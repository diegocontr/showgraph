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
@st.cache_data
def load_graph(file_path):
    """Loads a graph from a node-link JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, directed=True, multigraph=False)

# --- Sidebar Controls ---
st.sidebar.header("Controls")

# Correctly locate the data folder relative to the project root
# The script is in app/, so we go up one level to the project root.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
data_dir = os.path.join(project_root, "data")

os.makedirs(data_dir, exist_ok=True)
json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]

if not json_files:
    st.error("No graph JSON files found in the 'data' directory.")
    st.info("To get started, run the data generation script from your terminal: `python app/create_default_graph.py`")
    st.stop()

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
# Handle navigation from right panel buttons
if st.session_state.get('nav_to_node'):
    sel = st.session_state.nav_to_node
    st.session_state.selected_node = sel
    st.session_state.search_query = sel
    st.session_state.nav_to_node = ''

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
    ["Default Physics (ForceAtlas2)", "From Pre-calculated Layout",  "Community Detection (Greedy Modularity)", "Hierarchical", "Kamada-Kawai", "Fruchterman-Reingold"],
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

simplify_chains = st.sidebar.toggle(
    "Simplify linear chains",
    value=False,
    help="Hide nodes in simple A->B->C chains."
)

# --- New: Attribute Selection ---
st.sidebar.markdown("---")
st.sidebar.subheader("Attribute Display")
available_attrs = []
if G.nodes:
    # Get attributes from a sample node, assuming they are consistent
    sample_node = list(G.nodes())[0]
    # Attributes to exclude from the list (used for visualization)
    excluded_attrs = {'x', 'y', 'label', 'id', 'size', 'color', 'physics', 'title'}
    available_attrs = sorted([attr for attr in G.nodes[sample_node] if attr not in excluded_attrs])

selected_attrs = st.sidebar.multiselect(
    "Show attributes on hover:",
    options=available_attrs,
    default=[],
    help="Select which node attributes to show in the tooltip."
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
def create_ego_graph_view(full_graph, center_node, out_radius_hops, in_radius_hops, hide_source_nodes, layout, simplify_chains=False, attributes_to_show=None):
    if not center_node or center_node not in full_graph:
        return Network(height='750px', width='100%', bgcolor='#222222', font_color='white')

    if attributes_to_show is None:
        attributes_to_show = []

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
    
    if simplify_chains:
        while True:
            simplified_in_pass = False
            # Iterate over a copy of nodes as the graph will be modified
            for n in list(combined_g.nodes()):
                
                # Conditions for simplification
                is_candidate = (
                    n != center_node and
                    combined_g.in_degree(n) == 1 and
                    combined_g.out_degree(n) == 1
                )
                
                if is_candidate:
                    pred = list(combined_g.predecessors(n))[0]
                    succ = list(combined_g.successors(n))[0]
                    
                    # Don't simplify if it creates a self-loop
                    if pred != succ:
                        combined_g.add_edge(pred, succ)
                        combined_g.remove_node(n)
                        simplified_in_pass = True
            
            if not simplified_in_pass:
                break

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
            if is_center:
                color = "#ff4d4d" # Keep center node distinct
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

        # --- Build hover tooltip ---
        # Create a plain text title, as HTML was not rendering correctly.
        # Pyvis/vis.js should convert newlines to <br> tags automatically.
        title = str(attrs.get('label', node))
        if attributes_to_show:
            details = []
            for attr_key in attributes_to_show:
                attr_val = full_graph.nodes[node].get(attr_key, 'N/A')
                details.append(f"{attr_key.replace('_', ' ').title()}: {attr_val}")
            if details:
                title += "\n---\n" + "\n".join(details)

        net.add_node(
            node,
            label=attrs.get('label', node),
            title=title,
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
    
    # Create columns for graph and navigation panel
    graph_col, nav_col = st.columns([3, 1])
    
    with graph_col:
        net_viz = create_ego_graph_view(G, selected_node, out_radius, in_radius, hide_sources, layout_option, simplify_chains, selected_attrs)
        
        # --- Graph Rendering ---
        try:
            html_code = net_viz.generate_html()
            components.html(html_code, height=800, scrolling=True)
        except Exception as e:
            st.error(f"An error occurred while displaying the graph: {e}")
    
    with nav_col:
        st.markdown("#### Navigate to:")
        
        # Get neighbors
        out_nbrs = sorted(G.successors(selected_node))
        in_nbrs = sorted(G.predecessors(selected_node))
        
        # Helper function to get node color based on type
        def get_node_color(node, is_outgoing, is_incoming):
            if is_incoming and is_outgoing:
                return "#9933ff"  # Both paths (purple)
            elif is_incoming:
                return "#33cc33"  # Incoming path (green)
            elif is_outgoing:
                return "#ffaa00"  # Outgoing path (orange)
            else:
                return "#66a3ff"  # Default (blue)
        
        # Create sets for efficient lookup
        out_set = set(out_nbrs)
        in_set = set(in_nbrs)
        
        # Display outgoing neighbors
        if out_nbrs:
            st.markdown("**Outgoing Neighbors:**")
            for nbr in out_nbrs:
                is_both = nbr in in_set
                color = get_node_color(nbr, True, is_both)
                
                # Create columns for colored indicator and button
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    st.markdown(f"<span style='color:{color}; font-size: 16px;'>●</span>", unsafe_allow_html=True)
                with col2:
                    if st.button(f"→ {nbr}", key=f"out_nav_{nbr}", help=f"Navigate to {nbr}", use_container_width=True):
                        st.session_state.nav_to_node = nbr
                        st.rerun()
        
        # Display incoming neighbors
        if in_nbrs:
            st.markdown("**Incoming Neighbors:**")
            for nbr in in_nbrs:
                is_both = nbr in out_set
                color = get_node_color(nbr, is_both, True)
                
                # Create columns for colored indicator and button
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    st.markdown(f"<span style='color:{color}; font-size: 16px;'>●</span>", unsafe_allow_html=True)
                with col2:
                    if st.button(f"← {nbr}", key=f"in_nav_{nbr}", help=f"Navigate to {nbr}", use_container_width=True):
                        st.session_state.nav_to_node = nbr
                        st.rerun()
        
        if not out_nbrs and not in_nbrs:
            st.info("No connected neighbors found.")
        
        # Add a small legend for the navigation panel
        st.markdown("---")
        st.markdown("**Colors:**")
        st.markdown("""
        <div style="font-size: 12px;">
        <span style='color:#ffaa00;'>●</span> Outgoing<br>
        <span style='color:#33cc33;'>●</span> Incoming<br>
        <span style='color:#9933ff;'>●</span> Both
        </div>
        """, unsafe_allow_html=True)

# --- New: Interactive neighbor buttons ---
# if selected_node:
#     out_nbrs = sorted(G.successors(selected_node))
#     in_nbrs  = sorted(G.predecessors(selected_node))

#     st.sidebar.markdown("---")
#     st.sidebar.subheader("Jump to Neighbor")
#     with st.sidebar.expander("Outgoing neighbors"):
#         for nbr in out_nbrs:
#             if st.button(f"→ {nbr}", key=f"out_{nbr}"):
#                 st.session_state.selected_node = nbr
#                 st.session_state.search_query = nbr
#                 st.rerun()

#     with st.sidebar.expander("Incoming neighbors"):
#         for nbr in in_nbrs:
#             if st.button(f"← {nbr}", key=f"in_{nbr}"):
#                 st.session_state.selected_node = nbr
#                 st.session_state.search_query = nbr
#                 st.rerun()

# --- Instructions and Info ---
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### How to Use")
    st.markdown("""
    - **Search & Select:** Find a node to focus on.
    - **Traverse:** Double-click any node in the view to make it the new focus.
    - **Navigate:** Use the right panel buttons to jump to connected neighbors.
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