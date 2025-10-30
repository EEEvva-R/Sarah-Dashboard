import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

## Page config 
st.set_page_config(
    page_title="📊Sarah's 1:1 Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Sarah's 1:1 Dashboard")

## Load data
@st.cache_data
def load_data():
    df = pd.read_excel("Raw_text.xlsx")
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')

    # Status logic
    today = pd.Timestamp.today()
    def status(row):
        if pd.isna(row['due_date']):
            return "No Due"
        elif row['due_date'] < today:
            return "Overdue"
        elif (row['due_date'] - today).days <= 7:
            return "Due Soon"
        else:
            return "On Track"
    df['status'] = df.apply(status, axis=1)
    return df

df = load_data()

## Sidebar filters
st.sidebar.header("Filters")
person_sel = st.sidebar.multiselect("Select person", df['person'].unique(), default=df['person'].unique())
feature_sel = st.sidebar.multiselect("Select category", df['feature_category'].unique(), default=df['feature_category'].unique())
sent_sel = st.sidebar.multiselect("Select sentiment", df['sentiment'].unique(), default=df['sentiment'].unique())

df_filt = df[
    df['person'].isin(person_sel) &
    df['feature_category'].isin(feature_sel) &
    df['sentiment'].isin(sent_sel)
]

## KPI cards
total_topics = len(df_filt)
pos = (df_filt['sentiment'] == '+').sum()
mix = (df_filt['sentiment'] == '±').sum()
neg = (df_filt['sentiment'] == '-').sum()
due_soon = (df_filt['status'] == 'Due Soon').sum()
overdue = (df_filt['status'] == 'Overdue').sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total Topics", total_topics)
c2.metric("Positive", pos)
c3.metric("Mixed", mix)
c4.metric("Negative", neg)
c5.metric("Due Soon", due_soon)
c6.metric("Overdue", overdue)

st.markdown("---")

## Insights
st.subheader("💡 Auto Insights")

def _safe_pct(num, den):
    return 0 if den == 0 else round(100 * num / den)

def build_insights(df):
    insights = []
    if df.empty:
        return ["No data under current filters."]

    # 1) Overall focus
    cat_counts = df['feature_category'].value_counts()
    if not cat_counts.empty:
        top_cat = cat_counts.idxmax()
        top_cat_pct = _safe_pct(cat_counts.max(), len(df))
        insights.append(f"Focus is on **{top_cat}** ({top_cat_pct}% of topics).")

    # 2) Per-person snapshot (focus + sentiment + urgency)
    for p in sorted(df['person'].dropna().unique()):
        sub = df[df['person'] == p]
        if sub.empty:
            continue
        # Top category for this person
        p_cat_counts = sub['feature_category'].value_counts()
        p_top_cat = p_cat_counts.idxmax() if not p_cat_counts.empty else "N/A"
        p_top_pct = _safe_pct(p_cat_counts.max() if not p_cat_counts.empty else 0, len(sub))
        # Sentiment
        p_pos = (sub['sentiment'] == '+').sum()
        p_mix = (sub['sentiment'] == '±').sum()
        p_neg = (sub['sentiment'] == '-').sum()
        pos_rate = _safe_pct(p_pos, len(sub))
        # Urgency
        p_due = sub['status'].isin(['Due Soon', 'Overdue']).sum()
        insights.append(
            f"**{p}**: mainly **{p_top_cat}** ({p_top_pct}%). Sentiment → +:{p_pos}, ±:{p_mix}, -:{p_neg} "
            f"(**{pos_rate}% positive**). Urgent items: **{p_due}**."
        )

    # 3) Risk & urgency signal
    due = df[df['status'].isin(['Due Soon', 'Overdue'])].copy()
    if not due.empty:
        overdue_cnt = (due['status'] == 'Overdue').sum()
        insights.append(f"Urgency: {len(due)} items require attention (**{overdue_cnt} overdue**).")
        # list the next 3 deadlines
        up_next = due.sort_values('due_date').head(3)
        labels = [f"{r['due_date'].date()} – {r['person']}: *{r['topic']}*" for _, r in up_next.iterrows()]
        insights.append("Next deadlines → " + " | ".join(labels))

    # 4) Wins vs. friction
    wins = df[df['sentiment'] == '+']
    frictions = df[(df['sentiment'] != '+') & df['feature_category'].isin(
        ['Risk / Incident Management', 'Process / Quality Metrics', 'Projects / Execution']
    )]
    if not wins.empty:
        top_win_cat = wins['feature_category'].value_counts().idxmax()
        insights.append(f"Wins cluster in **{top_win_cat}** (e.g., {min(3, len(wins))} recent positives).")
    if not frictions.empty:
        top_frict_cat = frictions['feature_category'].value_counts().idxmax()
        insights.append(f"Friction hotspots: **{top_frict_cat}** (prioritize coaching/unblocking).")

    return insights

for line in build_insights(df_filt):
    st.markdown(f"- {line}")

# Optional: expandable detail blocks
with st.expander("Upcoming deadlines (next 7 days)"):
    next7 = df_filt[
        (df_filt['due_date'].notna()) &
        ((df_filt['due_date'] - pd.Timestamp.today()).dt.days.between(0, 7, inclusive="both"))
    ].sort_values('due_date')
    if next7.empty:
        st.write("No deadlines in the next 7 days.")
    else:
        st.dataframe(next7[['person','topic','action','due_date','status']], use_container_width=True)

with st.expander("Risk items (Mixed/Negative or Urgent)"):
    risk = df_filt[
        (df_filt['sentiment'].isin(['±','-'])) | (df_filt['status'].isin(['Due Soon','Overdue']))
    ][['person','feature_category','topic','sentiment','status','due_date']]
    if risk.empty:
        st.write("No risk-flagged items under current filters.")
    else:
        st.dataframe(risk.sort_values(['status','due_date'], ascending=[False, True]), use_container_width=True)


## Charts
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("🔖 Topic Distribution by Feature Category")
    cat_counts = df_filt['feature_category'].value_counts().reset_index()
    cat_counts.columns = ['feature_category', 'count']
    fig1 = px.bar(cat_counts, x='feature_category', y='count',
                  color='feature_category', text='count',
                  color_discrete_sequence=px.colors.qualitative.Set2)
    fig1.update_layout(xaxis_title="", yaxis_title="Count", showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Sentiment Breakdown")
    sent_counts = df_filt['sentiment'].value_counts().reset_index()
    sent_counts.columns = ['sentiment', 'count']
    fig2 = px.pie(sent_counts, values='count', names='sentiment',
                  color='sentiment',
                  color_discrete_map={'+': '#2ecc71', '±': '#f1c40f', '-': '#e74c3c'})
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

## Upcoming & Overdue Actions
st.subheader("✅ Action Tracker")
df_due = df_filt[df_filt['status'].isin(['Due Soon', 'Overdue'])].copy()

if not df_due.empty:
    def highlight_status(val):
        color = ''
        if val == 'Overdue':
            color = 'background-color: #f8d7da'  # red
        elif val == 'Due Soon':
            color = 'background-color: #fff3cd'  # yellow
        return color

    st.dataframe(
        df_due[['person','topic','action','due_date','status']].style.applymap(highlight_status, subset=['status']),
        use_container_width=True
    )
else:
    st.info("✅ No upcoming or overdue actions — all items on track!")

st.markdown("---")

## Conversation Explorer
st.subheader("💬 Conversation Explorer")
st.write("Browse full 1:1 raw text for selected topics.")
sel_topic = st.selectbox("Select a topic to view details:", df_filt['topic'].unique())

sel_row = df_filt[df_filt['topic'] == sel_topic].iloc[0]
st.markdown(f"**Person:** {sel_row['person']} | **Category:** {sel_row['feature_category']} | **Sentiment:** {sel_row['sentiment']} | **Due:** {sel_row['due_date'].date() if pd.notna(sel_row['due_date']) else 'N/A'}")

st.text_area("Conversation Text", sel_row['raw_text'], height=300)