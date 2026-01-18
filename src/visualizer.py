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