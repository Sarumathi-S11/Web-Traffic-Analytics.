# Web Traffic Analytics

## Project overview
A Python analytics project that examines website event data to understand user behavior, engagement, traffic sources, page performance, conversion funnel drop-offs, and common page-to-page journeys.

## Objectives
- Measure page views, sessions, unique visitors, average pages per session, and session duration.
- Compare engagement across traffic sources and device types.
- Identify funnel drop-off points from landing pages through signup and checkout.
- Map common page-to-page transitions.
- Recommend improvements to website engagement and conversion.

## Project structure
```text
Web-Traffic-Analytics/
├── data/web_traffic_raw.csv
├── src/web_traffic_analysis.py
├── reports/ (cleaned data, KPI, funnel, journeys, recommendations)
├── visualizations/ (4 charts)
├── requirements.txt
└── README.md
```

## How to run
Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt
python src/web_traffic_analysis.py
```

To use another dataset with the same column structure:
```bash
python src/web_traffic_analysis.py --input path/to/events.csv --output-dir reports
```

## Dataset columns
`session_id`, `user_id`, `event_timestamp`, `page_path`, `event_type`, `traffic_source`, `device`, `country`, `page_load_seconds`.

## Metrics and analysis
- Page views and unique sessions per page
- Average session duration and pages per session
- Single-page session rate (a simple bounce proxy)
- Event-based conversion rate
- Engagement by traffic source and device
- Funnel reach and percentage drop-off between steps
- Most frequent page-to-page transitions

## Data integrity and interpretation
The included event data is synthetic and created for learning. The raw file is preserved. Exact duplicate events are removed; required identifiers, timestamps, and page paths are validated; text and numeric fields are standardized. Session duration is calculated as the difference between the first and last recorded event in a session. A session with only one event has a measured duration of zero; this is not necessarily actual time spent on the website.

The funnel counts sessions that visited each listed page at least once. The transition table counts consecutive page events within each session. These metrics are descriptive and do not establish causation. For production analytics, define session timeout rules, event semantics, consent requirements, and bot filtering before interpreting results.
