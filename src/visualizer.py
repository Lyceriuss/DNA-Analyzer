import plotly.graph_objects as go
import pandas as pd
import os

def create_polar_chart(summary_df, output_path):
    """
    Generates a static PNG polar chart from the domain summary DataFrame.
    """
    if summary_df.empty:
        return

    # Prepare data for Plotly
    df = summary_df.copy()
    domains = df["Domain"].tolist()
    
    # Values for the rings
    neg_r = df["Negative"].values
    base_r = df["Baseline"].values
    pos_r = df["Positive"].values
    
    # Calculate angular axis
    N = len(domains)
    theta = [i * (360 / N) for i in range(N)]
    width = [360 / N] * N
    
    # Stacking logic for the chart
    base_layer1 = neg_r
    base_layer2 = neg_r + base_r

    fig = go.Figure()

    # 1. Negative Ring (Red)
    fig.add_trace(go.Barpolar(
        r=neg_r,
        base=0,
        theta=theta,
        width=width,
        marker=dict(color="rgba(231, 76, 60, 0.9)", line=dict(color="white", width=1)),
        name="Negative (↓)"
    ))
    
    # 2. Baseline Ring (Green - Transparent)
    fig.add_trace(go.Barpolar(
        r=base_r,
        base=base_layer1,
        theta=theta,
        width=width,
        marker=dict(color="rgba(39, 174, 96, 0.4)", line=dict(color="white", width=1)),
        name="Baseline (~)"
    ))

    # 3. Positive Ring (Blue)
    fig.add_trace(go.Barpolar(
        r=pos_r,
        base=base_layer2,
        theta=theta,
        width=width,
        marker=dict(color="rgba(52, 152, 219, 0.9)", line=dict(color="white", width=1)),
        name="Positive (↑)"
    ))

    fig.update_layout(
        margin=dict(t=30, b=30, l=80, r=80), 
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(showticklabels=False, ticks=''),
            angularaxis=dict(
                tickvals=theta,
                ticktext=domains,
                tickfont=dict(size=12, family="Arial", color="#333"), 
                rotation=90,
                direction="clockwise"
            )
        ),
        legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
        width=800,
        height=800
    )

    try:
        # Save static image
        fig.write_image(output_path, scale=2)
        print(f"✅ Polar chart saved to {output_path}")
    except Exception as e:
        print(f"⚠️ Failed to save polar chart (Kaleido error?): {e}")


def create_heritage_pie_chart(df, output_path, parent1_name="Mom", parent2_name="Dad"):
    """Generates a static PNG donut chart using Plotly, matching the polar chart's engine."""
    print(f"📊 [DEBUG] Starting pie chart generation for {parent1_name} and {parent2_name}...")
    
    if df is None:
        print("⚠️ [DEBUG] Aborted: The DataFrame passed is None.")
        return
        
    if df.empty:
        print("⚠️ [DEBUG] Aborted: The DataFrame is empty.")
        return
        
    if 'Inheritance_Source' not in df.columns:
        print(f"⚠️ [DEBUG] Aborted: 'Inheritance_Source' not found. Available columns: {df.columns.tolist()}")
        return

    counts = df['Inheritance_Source'].value_counts()
    labels = counts.index.tolist()
    values = counts.values.tolist()
    
    print(f"📊 [DEBUG] Data extracted: {dict(zip(labels, values))}")

    if not values: 
        print("⚠️ [DEBUG] Aborted: No valid data values to chart.")
        return

    # Map colors to match the PDF tables
    color_map = {
        f"Match: {parent1_name}": "rgba(231, 76, 60, 0.9)",   # Red
        f"Match: {parent2_name}": "rgba(52, 152, 219, 0.9)",  # Blue
        "Both Sides": "rgba(155, 89, 182, 0.9)",              # Purple
        "Mixed / Recombined": "rgba(241, 196, 15, 0.9)",      # Yellow
        "Unknown": "rgba(149, 165, 166, 0.9)",                # Gray
        "Relatives Not Tested": "rgba(236, 240, 241, 0.9)"
    }
    marker_colors = [color_map.get(l, "rgba(189, 195, 199, 0.9)") for l in labels]

    print("📊 [DEBUG] Drawing figure...")
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.45,
        marker=dict(colors=marker_colors, line=dict(color='#ffffff', width=2)),
        textinfo='percent', textfont=dict(size=14, color='white', family="Arial")
    )])

    fig.update_layout(
        title=dict(text="Inherited Trait Distribution", font=dict(size=18, color="#2c3e50", family="Arial", weight="bold"), x=0.5),
        margin=dict(t=50, b=20, l=20, r=150),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="v", y=0.5, x=1.02, xanchor="left", yanchor="middle"),
        width=700, height=450
    )

    try:
        print(f"📊 [DEBUG] Attempting to save to {output_path}...")
        fig.write_image(output_path, scale=2)
        print(f"✅ Heritage pie chart saved to {output_path}")
    except Exception as e:
        print(f"⚠️ Failed to save heritage pie chart: {e}")