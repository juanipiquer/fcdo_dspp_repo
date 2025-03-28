import collections
import itertools
import networkx as nx
import numpy as np
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State
import plotly.graph_objects as go
from iso3166 import countries_by_alpha2

df = pd.read_csv("openalex_combined_dataset.csv")

# UK's official name is too long. Need to shorten
country_name_overrides = {
    "GB": "United Kingdom"
}

# dash app
app = Dash(__name__)

# layout. years and topic filter
app.layout = html.Div([
    html.H3("Country Collaboration Network", style={'font-family': 'Helvetica'}),
    dcc.Dropdown(
        id="topic-filter",
        options=[
            {"label": "Artificial Intelligence", "value": "Artificial Intelligence"},
            {"label": "Engineering Biology", "value": "Engineering Biology"},
            {"label": "Quantum Technology", "value": "Quantum Technology"}
        ],
        value="Artificial Intelligence",
        clearable=False,
        style={'font-family': 'Helvetica'}
    ),
    dcc.RangeSlider(
        id="year-slider",
        min=2000,
        max=2025,
        step=1,
        value=[2000, 2025],
        marks={year: {'label': str(year), 'style': {'font-family': 'Helvetica', 'writing-mode': 'vertical-lr'}} for year in range(2000, 2026, 1)},
    ),
    
    html.Div(style={'height': '12px'}),

    dcc.Dropdown(
        id="label-selection",
        options=[],
        placeholder="Select Country to highlight",
        style={'font-family': 'Helvetica'}
    ),
    html.Div([
        dcc.Graph(id="country-network-graph", clear_on_unhover=True, 
        config={'scrollZoom': True}, style={'flex': '1', 'height': '550px'}),
        html.Div(id="hovered-country-pairings-container", children=[
            html.Div(id="hovered-country-name", style={'font-size': '20px', 'font-family': 'Helvetica'}),
            html.Div(id="hovered-country-pairings", style={'font-family': 'Helvetica'})
        ], style={'padding': '10px'})
    ], style={'display': 'flex', 'flex-direction': 'column'})
])

@app.callback(
    [Output("country-network-graph", "figure"),
     Output("hovered-country-name", "children"),
     Output("hovered-country-pairings", "children"),
     Output("label-selection", "options")],
    [Input("topic-filter", "value"), Input("year-slider", "value"), Input("country-network-graph", "hoverData"), Input("label-selection", "value")]
)
def update_graph(selected_topic, selected_years, hoverData, selected_label):
    
    filtered_df = df[(df['Topic'] == selected_topic) & (df['Year'] >= selected_years[0]) & (df['Year'] <= selected_years[1])]
    
    #
    country_edges = []
    for _, row in filtered_df.iterrows():
        country_codes = list(set(row['Institution Country'].split(', ')))
        country_names = [
            country_name_overrides.get(code, countries_by_alpha2[code].name if code in countries_by_alpha2 else code)
            for code in country_codes
        ]
        country_edges.extend(itertools.combinations(country_names, 2))
    
    country_pairs = collections.Counter(country_edges)
    G = nx.Graph()
    for pair, weight in country_pairs.items():
        G.add_edge(pair[0], pair[1], weight=weight)
    
    pos = nx.spring_layout(G, seed=42, k=0.3 * (1 / np.sqrt(len(G.nodes()))))
    
    country_options = [{"label": country, "value": country} for country in G.nodes()]
    
    #this should make the hover tooltip work...maybe? 
    hovered_node = None
    if hoverData and 'points' in hoverData and hoverData['points']:
        first_point = hoverData['points'][0]
        if 'text' in first_point:
            hovered_node = first_point['text'].split('<br>')[0]
    
    highlighted_nodes = set([selected_label]) if selected_label else set()
    highlighted_edges = set()
    if hovered_node:
        highlighted_nodes.add(hovered_node)
        highlighted_nodes.update([neighbor for neighbor in G.neighbors(hovered_node)])
    if selected_label:
        highlighted_nodes.update([neighbor for neighbor in G.neighbors(selected_label)])
        highlighted_edges.update([(selected_label, neighbor) for neighbor in G.neighbors(selected_label)])
    
    hovered_pairings = []
    hovered_country_label = "Top 3 Collaborators"
    selected_country = hovered_node if hovered_node else selected_label
    if selected_country:
        hovered_country_label = f"Top 3 Collaborators for {selected_country}"
        
        all_collaborators = sorted(
            [(a, b, d['weight']) for a, b, d in G.edges(data=True) if a == selected_country or b == selected_country],
            key=lambda x: x[2], reverse=True
        )
        
        unique_collaborators = list(dict.fromkeys([(collab[0], collab[1]) for collab in all_collaborators if collab[0] != collab[1]]))
        
        top_collaborators = unique_collaborators[:3]
        
        hovered_pairings = [html.Li(f"{collab[0]} - {collab[1]}") for collab in top_collaborators]
    
    edge_x, edge_y = [], []
    for edge in highlighted_edges:
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    node_x, node_y, node_size, node_text, node_colors, node_labels = [], [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_size.append((G.degree(node) / max(1, max(dict(G.degree()).values()))) * 30 + 10)
        node_text.append(f"{node}<br><b>Unique Country Pairings:</b> {G.degree(node)}")
        node_labels.append(node if node == selected_label or node == hovered_node else "")
        node_colors.append("green" if node == selected_label else ("red" if node in highlighted_nodes else "blue"))
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.5, color="red"),
        hoverinfo="none"
    ))
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=node_size, color=node_colors),
        text=node_labels, textposition="top center",
        hoverinfo="text",
        customdata=node_text,
        hovertemplate="%{customdata}<extra></extra>",
        name=""
    ))
    fig.update_layout(title=f"{selected_topic} Collaborations ({selected_years[0]}-{selected_years[1]})", showlegend=False, uirevision="network",
                      xaxis=dict(showgrid=False, showticklabels=False, ticks='', zeroline=False), 
                      yaxis=dict(showgrid=False, showticklabels=False, ticks='', zeroline=False), 
                      template="plotly_white", 
                      font=dict(family="Helvetica", size=12), 
                      plot_bgcolor='rgba(0,0,0,0)')
                      
                      
    return fig, hovered_country_label, hovered_pairings if hovered_pairings else [html.Li("None")], country_options

if __name__ == "__main__":
    app.run_server(debug=True, port=8500)