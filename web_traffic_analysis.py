"""Web traffic analytics: cleaning, metrics, funnel and journey analysis."""
from pathlib import Path
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REQUIRED = ["session_id","user_id","event_timestamp","page_path","event_type",
            "traffic_source","device","country","page_load_seconds"]

def load_clean(path):
    df=pd.read_csv(path)
    df.columns=df.columns.str.strip().str.lower().str.replace(r"\s+","_",regex=True)
    missing=sorted(set(REQUIRED)-set(df.columns))
    if missing: raise ValueError(f"Missing required columns: {missing}")
    rows_before=len(df)
    duplicate_count=int(df.duplicated().sum())
    df=df.drop_duplicates().copy()
    for col in ["session_id","user_id","page_path","event_type","traffic_source","device","country"]:
        df[col]=df[col].astype("string").str.strip()
    df["event_timestamp"]=pd.to_datetime(df["event_timestamp"],errors="coerce")
    df["page_load_seconds"]=pd.to_numeric(df["page_load_seconds"],errors="coerce")
    df=df.dropna(subset=["session_id","user_id","event_timestamp","page_path"])
    df["page_path"]=df["page_path"].str.replace(r"/+$","",regex=True).replace("","/")
    for col in ["event_type","traffic_source","device","country"]:
        df[col]=df[col].str.title()
    df["page_load_seconds"]=df["page_load_seconds"].fillna(df["page_load_seconds"].median())
    df.loc[df["page_load_seconds"]<0,"page_load_seconds"]=np.nan
    df["page_load_seconds"]=df["page_load_seconds"].fillna(df["page_load_seconds"].median())
    df=df.sort_values(["session_id","event_timestamp"]).reset_index(drop=True)
    summary={"rows_before":rows_before,"rows_after":len(df),"exact_duplicates_removed":duplicate_count,
             "missing_values_after_cleaning":int(df.isna().sum().sum()),
             "unique_sessions":int(df["session_id"].nunique())}
    return df,summary

def analyze(df,outdir,visual_dir):
    outdir=Path(outdir); visual_dir=Path(visual_dir)
    outdir.mkdir(parents=True,exist_ok=True); visual_dir.mkdir(parents=True,exist_ok=True)
    sess=df.groupby("session_id").agg(
        user_id=("user_id","first"),session_start=("event_timestamp","min"),
        session_end=("event_timestamp","max"),page_views=("page_path","count"),
        landing_page=("page_path","first"),exit_page=("page_path","last"),
        traffic_source=("traffic_source","first"),device=("device","first"),
        country=("country","first"),events=("event_type",lambda x:" > ".join(x.astype(str)))
    ).reset_index()
    sess["session_duration_seconds"]=(sess["session_end"]-sess["session_start"]).dt.total_seconds()
    # Single-event sessions have zero observed elapsed duration; preserve as zero.
    sess["converted"]=sess["events"].str.contains("Form_Submit|Purchase|Thank_You",case=False,regex=True)
    sess.to_csv(outdir/"session_summary.csv",index=False)

    total_sessions=len(sess)
    total_views=len(df)
    avg_duration=float(sess["session_duration_seconds"].mean()) if total_sessions else 0
    bounce_rate=float((sess["page_views"]==1).mean()*100) if total_sessions else 0
    conversion_rate=float(sess["converted"].mean()*100) if total_sessions else 0
    kpis=pd.DataFrame([
        ["Total page events",total_views],["Total sessions",total_sessions],
        ["Unique visitors",df["user_id"].nunique()],["Average page views per session",round(sess["page_views"].mean(),2)],
        ["Average session duration (seconds)",round(avg_duration,2)],
        ["Single-page session rate (%)",round(bounce_rate,2)],
        ["Event-based conversion rate (%)",round(conversion_rate,2)]
    ],columns=["metric","value"])
    kpis.to_csv(outdir/"kpi_summary.csv",index=False)

    page_perf=df.groupby("page_path").agg(page_views=("page_path","size"),
        unique_sessions=("session_id","nunique"),avg_load_seconds=("page_load_seconds","mean")).reset_index()
    page_perf["session_share_pct"]=(page_perf["unique_sessions"]/total_sessions*100).round(2)
    page_perf=page_perf.sort_values("page_views",ascending=False)
    page_perf.to_csv(outdir/"page_performance.csv",index=False)

    source=sess.groupby("traffic_source").agg(sessions=("session_id","count"),
        avg_duration_seconds=("session_duration_seconds","mean"),
        single_page_sessions=("page_views",lambda x:(x==1).sum()),
        conversion_rate_pct=("converted",lambda x:round(x.mean()*100,2))).reset_index()
    source["single_page_rate_pct"]=(source["single_page_sessions"]/source["sessions"]*100).round(2)
    source.to_csv(outdir/"traffic_source_performance.csv",index=False)

    device=sess.groupby("device").agg(sessions=("session_id","count"),
        avg_page_views=("page_views","mean"),
        avg_duration_seconds=("session_duration_seconds","mean"),
        conversion_rate_pct=("converted",lambda x:round(x.mean()*100,2))).reset_index()
    device.to_csv(outdir/"device_performance.csv",index=False)

    # Funnel based on whether each session visited each step at least once.
    funnel_pages=["/","/products","/pricing","/signup","/checkout","/thank-you"]
    funnel=[]
    for page in funnel_pages:
        count=int(df[df["page_path"]==page]["session_id"].nunique())
        funnel.append({"funnel_step":page,"sessions_reached":count,
                       "pct_of_all_sessions":round(count/total_sessions*100,2) if total_sessions else 0})
    funnel_df=pd.DataFrame(funnel)
    funnel_df["drop_off_from_previous_pct"]=(
        (1-funnel_df["sessions_reached"].div(funnel_df["sessions_reached"].shift(1)))*100
    ).round(2)
    funnel_df.to_csv(outdir/"conversion_funnel.csv",index=False)

    # Common page-to-page transitions, preserving within-session event order.
    transitions=[]
    for sid,g in df.groupby("session_id"):
        seq=g["page_path"].tolist()
        transitions.extend(zip(seq[:-1],seq[1:]))
    trans=pd.DataFrame(transitions,columns=["from_page","to_page"])
    if len(trans):
        trans=trans.value_counts().rename("transition_count").reset_index()
        trans.to_csv(outdir/"top_user_journeys.csv",index=False)
    else:
        pd.DataFrame(columns=["from_page","to_page","transition_count"]).to_csv(outdir/"top_user_journeys.csv",index=False)

    # Charts
    plt.figure(figsize=(7,4)); page_perf.head(10).sort_values("page_views").plot(
        x="page_path",y="page_views",kind="barh",legend=False)
    plt.title("Top Pages by Page Views"); plt.xlabel("Page views"); plt.ylabel("Page")
    plt.tight_layout(); plt.savefig(visual_dir/"top_pages.png",dpi=150); plt.close()

    plt.figure(figsize=(7,4)); sess["session_duration_seconds"].clip(upper=600).plot(kind="hist",bins=25)
    plt.title("Session Duration Distribution (capped at 10 minutes)"); plt.xlabel("Duration (seconds)")
    plt.tight_layout(); plt.savefig(visual_dir/"session_duration.png",dpi=150); plt.close()

    plt.figure(figsize=(7,4)); funnel_df.plot(x="funnel_step",y="sessions_reached",kind="bar",legend=False)
    plt.title("Conversion Funnel"); plt.xlabel("Funnel page"); plt.ylabel("Sessions reached")
    plt.tight_layout(); plt.savefig(visual_dir/"conversion_funnel.png",dpi=150); plt.close()

    plt.figure(figsize=(7,4)); source.sort_values("sessions").plot(x="traffic_source",y="sessions",kind="bar",legend=False)
    plt.title("Sessions by Traffic Source"); plt.xlabel("Traffic source"); plt.ylabel("Sessions")
    plt.tight_layout(); plt.savefig(visual_dir/"traffic_sources.png",dpi=150); plt.close()

    recommendations=[
        ["High single-page session rate","Improve landing-page relevance, page speed, and calls to action; test changes with A/B experiments."],
        ["Large funnel drop-off before signup","Simplify navigation and signup forms; clarify product value and reduce unnecessary steps."],
        ["Low engagement from a traffic source","Align landing-page content with the source campaign and review audience targeting."],
        ["Long page load times","Optimize images, scripts, caching, and mobile performance on the slowest pages."],
        ["Device-level engagement differences","Review responsive layouts and test key journeys on devices with lower conversion or engagement."]
    ]
    pd.DataFrame(recommendations,columns=["potential_issue","recommended_action"]).to_csv(outdir/"engagement_recommendations.csv",index=False)

    return kpis,funnel_df,trans if len(transitions) else pd.DataFrame()

def main(input_path,output_dir):
    out=Path(output_dir)
    df,summary=load_clean(input_path)
    df.to_csv(out/"web_traffic_cleaned.csv",index=False)
    pd.DataFrame([summary]).to_csv(out/"cleaning_summary.csv",index=False)
    kpis,funnel,trans=analyze(df,out,Path("visualizations"))
    print("Web traffic analysis completed.")
    print(kpis.to_string(index=False))
    print(f"Reports saved to: {out.resolve()}")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",default="data/web_traffic_raw.csv")
    parser.add_argument("--output-dir",default="reports")
    args=parser.parse_args()
    main(args.input,args.output_dir)
