import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import os
from networkx.readwrite import json_graph
import json
import random

# Set Streamlit page configuration
st.set_page_config(layout="wide", page_title="Scalable Graph Visualization")

st.title("Scalable Graph Visualization")
st.write("This app is designed for large graphs. Search for a node, then double-click on other nodes to traverse the graph.")


# --- Graph Loading and Setup ---
def setup_default_graph(data_folder="data", filename="large_default_graph.json"):
    """Creates a large default graph JSON file if it doesn't exist."""
    file_path = os.path.join(data_folder, filename)
    if not os.path.exists(file_path):
        st.info(f"Creating a large default graph file at '{file_path}' (300 nodes)...")
        os.makedirs(data_folder, exist_ok=True)
        
        G_sample = nx.fast_gnp_random_graph(n=300, p=0.015, seed=42, directed=True)
        mapping = {i: f"Node-{i}" for i in G_sample.nodes()}
        G_sample = nx.relabel_nodes(G_sample, mapping)

        pos = nx.spring_layout(G_sample, seed=42)
        
        for node in G_sample.nodes():
             G_sample.nodes[node]['x'] = pos[node][0] * 1500
             G_sample.nodes[node]['y'] = pos[node][1] * 1500
             G_sample.nodes[node]['label'] = node

        graph_json = json_graph.node_link_data(G_sample)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(graph_json, f, indent=4)
    return file_path

@st.cache_data
def load_graph(file_path):
    """Loads a graph from a node-link JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, directed=True, multigraph=False)

# --- Sidebar Controls ---
st.sidebar.header("Controls")

data_dir = "data"
os.makedirs(data_dir, exist_ok=True)
json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
if not json_files:
    setup_default_graph(data_dir)
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]

selected_file = st.sidebar.selectbox("Select a graph file:", json_files, key="selected_file_widget")

if 'graph' not in st.session_state or st.session_state.get('current_file') != selected_file:
    file_path = os.path.join(data_dir, selected_file)
    st.session_state.graph = load_graph(file_path)
    st.session_state.current_file = selected_file
    st.session_state.selected_node = None
    st.session_state.search_query = ""
    st.rerun()

G = st.session_state.graph
full_node_list = sorted(list(G.nodes()))

# --- Handle neighbor-traversal jumps before selected_node widget ---
if st.session_state.get('traverse_out'):
    sel = st.session_state.traverse_out
    st.session_state.selected_node = sel
    st.session_state.search_query = sel
    st.session_state.traverse_out = ''
if st.session_state.get('traverse_in'):
    sel = st.session_state.traverse_in
    st.session_state.selected_node = sel
    st.session_state.search_query = sel
    st.session_state.traverse_in = ''

st.sidebar.markdown("---")

# Simplified and corrected sidebar logic
# The text input's state is bound to 'search_query' in session state.
st.sidebar.text_input("Search for a node:", key="search_query")

# Filter nodes based on the content of the search box
if st.session_state.search_query:
    filtered_nodes = [node for node in full_node_list if st.session_state.search_query.lower() in node.lower()]
    if filtered_nodes:
        # Determine the index for the selectbox to sync with the current selection
        try:
            index = filtered_nodes.index(st.session_state.get('selected_node'))
        except (ValueError, TypeError):
            index = 0

        # This selectbox is bound to 'selected_node' in session state.
        # Changing its value will update the state and trigger a rerun.
        st.sidebar.selectbox(
            "Select a node to focus on:",
            filtered_nodes,
            index=index,
            key='selected_node'
        )
    else:
        st.sidebar.warning("No nodes match your search.")
        st.session_state.selected_node = None
else:
    # If search box is cleared, clear the selection as well
    st.session_state.selected_node = None

# Final selected_node is read from the session state
selected_node = st.session_state.get('selected_node')


st.sidebar.markdown("---")
st.sidebar.subheader("Display Options")

layout_option = st.sidebar.selectbox(
    "Graph Layout:",
    ["From Pre-calculated Layout", "Default Physics (ForceAtlas2)", "Community Detection (Greedy Modularity)", "Hierarchical", "Kamada-Kawai", "Fruchterman-Reingold"],
    key="layout_option",
    help="Pre-calculated is faster. Other layouts are dynamic or calculated on the fly."
)

out_radius = st.sidebar.slider("Outgoing Radius (hops):", 0, 5, 1, key="out_radius")
in_radius = st.sidebar.slider("Incoming Radius (hops):", 0, 5, 1, key="in_radius")

hide_sources = st.sidebar.toggle(
    "Hide source nodes",
    value=False,
    help="Hide nodes that have no incoming edges in the full graph."
)

# --- New: neighbor traversal dropdowns ---
if selected_node:
    out_nbrs = sorted(G.successors(selected_node))
    in_nbrs  = sorted(G.predecessors(selected_node))
    if out_nbrs or in_nbrs:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Traverse to Neighbor")
        sel_out = st.sidebar.selectbox("→ Outgoing:", [""] + out_nbrs, key="traverse_out")
        if sel_out:
            st.rerun()
        sel_in = st.sidebar.selectbox("← Incoming:", [""] + in_nbrs, key="traverse_in")
        if sel_in:
            st.rerun()

# --- Graph Visualization ---
def create_ego_graph_view(full_graph, center_node, out_radius_hops, in_radius_hops, hide_source_nodes, layout):
    if not center_node or center_node not in full_graph:
        return Network(height='750px', width='100%', bgcolor='#222222', font_color='white')

    out_ego_g = nx.DiGraph()
    if out_radius_hops > 0:
        out_ego_g = nx.ego_graph(full_graph, center_node, radius=out_radius_hops, undirected=False)

    in_ego_g = nx.DiGraph()
    if in_radius_hops > 0:
        in_ego_g = nx.ego_graph(full_graph.reverse(), center_node, radius=in_radius_hops, undirected=False)

    combined_g = nx.compose(out_ego_g, in_ego_g.reverse())
    if not combined_g.nodes:
        combined_g.add_node(center_node)

    if hide_source_nodes:
        nodes_to_remove = [node for node in combined_g.nodes() if full_graph.in_degree(node) == 0 and node != center_node]
        combined_g.remove_nodes_from(nodes_to_remove)
    
    net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True, cdn_resources='in_line')
    
    # --- Layout and Physics Configuration ---
    node_positions = {}
    community_map = {}
    
    # Calculate positions for NetworkX layouts
    if layout in ["Kamada-Kawai", "Fruchterman-Reingold"] and len(combined_g.nodes()) > 1:
        if layout == "Kamada-Kawai":
            node_positions = nx.kamada_kawai_layout(combined_g)
        else: # Fruchterman-Reingold
            node_positions = nx.fruchterman_reingold_layout(combined_g, seed=42)

    # Detect communities for coloring
    if layout == "Community Detection (Greedy Modularity)" and len(combined_g.nodes()) > 1:
        try:
            communities = nx.community.greedy_modularity_communities(combined_g.to_undirected())
            for i, community_set in enumerate(communities):
                for node in community_set:
                    community_map[node] = i
        except Exception:
            pass # Algorithm may fail on some graphs

    # Set pyvis options
    use_physics = layout in ["Default Physics (ForceAtlas2)", "Community Detection (Greedy Modularity)"]
    if layout == "Hierarchical":
        net.hrepulsion(node_distance=250)
    else:
        physics_options = f"""{{ "physics": {{ "enabled": {str(use_physics).lower()}, "solver": "forceAtlas2Based" }} }}"""
        net.set_options(physics_options)
    
    out_nodes = set(out_ego_g.nodes())
    in_nodes = set(in_ego_g.nodes())
    
    # Generate colors for communities
    community_colors = {}
    if community_map:
        num_communities = len(set(community_map.values()))
        if num_communities > 0:
            palette = [f'hsl({int(h)}, 80%, 60%)' for h in [i * 360.0/num_communities for i in range(num_communities)]]
            for node, community_id in community_map.items():
                community_colors[node] = palette[community_id]

    for node, attrs in combined_g.nodes(data=True):
        is_center = (node == center_node)
        
        # Determine node color
        if community_map and node in community_colors:
            color = community_colors[node]
            if is_center: color = "#ff4d4d" # Keep center node distinct
        else:
            color = "#ff4d4d" if is_center else ("#9933ff" if node in in_nodes and node in out_nodes else ("#33cc33" if node in in_nodes else ("#ffaa00" if node in out_nodes else "#66a3ff")))
        
        # Determine node position and physics
        pos_x, pos_y, node_physics = None, None, use_physics
        
        if layout == "From Pre-calculated Layout":
            pos_x = full_graph.nodes[node].get('x')
            pos_y = full_graph.nodes[node].get('y')
            node_physics = pos_x is None # Only apply physics if no position
        elif node_positions:
            pos_x = node_positions[node][0] * 1500
            pos_y = node_positions[node][1] * 1500
            node_physics = False
        elif layout == "Hierarchical":
            node_physics = True

        net.add_node(
            node,
            label=attrs.get('label', node),
            x=pos_x,
            y=pos_y,
            color=color,
            size=25 if is_center else 15,
            physics=node_physics
        )

    net.add_edges(combined_g.edges())
    return net


# --- Main App Body ---
if not selected_node:
    st.info("Search for a node in the sidebar to begin exploring the graph.")
else:
    st.markdown(f"### Exploring Neighborhood of **{selected_node}**")

net_viz = create_ego_graph_view(G, selected_node, out_radius, in_radius, hide_sources, layout_option)

# --- Graph Rendering ---
try:
    html_code = net_viz.generate_html()
    components.html(html_code, height=800, scrolling=True)
except Exception as e:
    st.error(f"An error occurred while displaying the graph: {e}")


# --- Instructions and Info ---
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### How to Use")
    st.markdown("""
    - **Search & Select:** Find a node to focus on.
    - **Traverse:** Double-click any node in the view to make it the new focus.
    - **Layout:** Choose a pre-calculated static layout or a dynamic one.
    """)
with col2:
    st.markdown("#### Legend")
    st.markdown(f"""
    - <span style='color:{"#ff4d4d"};'>&#9679;</span> **Center Node**
    - <span style='color:{"#ffaa00"};'>&#9679;</span> **Outgoing Path**
    - <span style='color:{"#33cc33"};'>&#9679;</span> **Incoming Path**
    - <span style'color:{"#9933ff"};'>&#9679;</span> **Both Paths**
    """, unsafe_allow_html=True)