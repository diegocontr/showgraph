import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import string
import os
from networkx.algorithms import community as nx_comm
from networkx.readwrite import json_graph
import json
import random

# Set Streamlit page configuration
st.set_page_config(layout="wide", page_title="Interactive Graph Visualization")

st.title("Interactive Directed Graph Visualization")

# --- Function to inject JS for click-to-select ---
def inject_click_handler(html_source):
    """Injects JavaScript into the pyvis HTML to send clicked node back to Streamlit."""
    js_code = """
    <script type="text/javascript">
        // Wait for the network to be initialized
        document.addEventListener('DOMContentLoaded', function() {
            // The 'network' object is created by pyvis in the global scope
            if (typeof network !== 'undefined') {
                network.on("selectNode", function(params) {
                    if (params.nodes.length > 0) {
                        const clickedNodeId = params.nodes[0];
                        // Use parent window to change URL, as component is in an iframe
                        const currentUrl = new URL(window.parent.location.href);
                        currentUrl.searchParams.set('select_node', clickedNodeId);
                        window.parent.location.href = currentUrl.toString();
                    }
                });
            }
        });
    </script>
    """
    # Inject the script just before the closing body tag
    return html_source.replace("</body>", js_code + "</body>")

# --- Graph Loading and Setup ---
def setup_default_graph(data_folder="app/data", filename="default_graph.json"):
    """Creates a default graph JSON file if it doesn't exist."""
    file_path = os.path.join(data_folder, filename)
    if not os.path.exists(file_path):
        st.info(f"Creating a default graph file at '{file_path}'...")
        os.makedirs(data_folder, exist_ok=True)
        
        # Create a sample graph
        G_sample = nx.DiGraph()
        G_sample.add_edges_from([
            ("A", "B"), ("A", "C"), ("B", "D"), ("C", "D"), ("D", "E"),
            ("E", "F"), ("E", "G"), ("F", "H"), ("I", "J"), ("J", "A"),
            ("K", "A"), ("L", "C"), ("C", "M")
        ])
        for u, v in G_sample.edges():
            G_sample.edges[u,v]['weight'] = round(random.uniform(1.0, 5.0), 2)

        graph_json = json_graph.node_link_data(G_sample)
        with open(file_path, 'w') as f:
            json.dump(graph_json, f, indent=4)
    return file_path

@st.cache_data
def load_graph(file_path):
    """Loads a graph from a node-link JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return json_graph.node_link_graph(data, directed=True, multigraph=False)

# --- Layout and Community Caching ---
@st.cache_data
def get_greedy_modularity_communities(_graph):
    undirected_G = _graph.to_undirected()
    communities_generator = nx_comm.greedy_modularity_communities(undirected_G)
    communities = list(communities_generator)
    return {node: i for i, comm in enumerate(communities) for node in comm}

@st.cache_data
def get_kamada_kawai_pos(_graph):
    return nx.kamada_kawai_layout(_graph)

@st.cache_data
def get_spring_pos(_graph):
    return nx.spring_layout(_graph, seed=42)

# --- State Management for Click-to-Select ---
clicked_node = st.query_params.get("select_node")
if clicked_node:
    st.session_state.selected_node = clicked_node
    st.query_params.clear()

# --- Sidebar Controls ---
st.sidebar.header("Controls")

# Widget to select graph file
data_dir = "app/data"
os.makedirs(data_dir, exist_ok=True)
json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
if not json_files:
    setup_default_graph(data_dir)
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]

selected_file = st.sidebar.selectbox(
    "Select a graph file:",
    json_files,
    key="selected_file_widget"
)

# Load graph based on selection and manage state
if 'graph' not in st.session_state or st.session_state.get('current_file') != selected_file:
    get_greedy_modularity_communities.clear()
    get_kamada_kawai_pos.clear()
    get_spring_pos.clear()
    
    file_path = os.path.join(data_dir, selected_file)
    st.session_state.graph = load_graph(file_path)
    st.session_state.current_file = selected_file
    st.session_state.selected_node = None
    st.rerun()

G = st.session_state.graph
node_list = [""] + sorted(list(G.nodes()))

st.sidebar.markdown("---")

layout_option = st.sidebar.selectbox(
    "Select a layout algorithm:",
    ["Default Physics (ForceAtlas2)", "Community Detection (Greedy Modularity)", "Hierarchical", "Kamada-Kawai", "Fruchterman-Reingold"],
    key="layout_option"
)

hide_source_neighbors = st.sidebar.toggle(
    "Hide source-node neighbors",
    value=False,
    help="If enabled, incoming neighbors that have no incoming connections themselves will not be highlighted."
)

st.sidebar.markdown("---")

search_query = st.sidebar.text_input("Search for a node:", key="search_query")
filtered_nodes = [node for node in node_list if search_query.lower() in node.lower()] if search_query else node_list

try:
    current_index = filtered_nodes.index(st.session_state.get("selected_node", ""))
except ValueError:
    current_index = 0

selected_node = st.sidebar.selectbox(
    "Select a node to highlight neighbors:",
    filtered_nodes,
    key="selected_node",
    index=current_index
)

# --- Graph Visualization ---
def create_interactive_graph(graph, selected_node, layout_option, hide_sources):
    net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', directed=True, cdn_resources='in_line')

    physics_options = ""
    if layout_option == "Hierarchical":
        physics_options = """{"layout": {"hierarchical": {"enabled": true, "sortMethod": "hubsize"}}, "physics": {"solver": "hierarchicalRepulsion"}}"""
    elif layout_option in ["Kamada-Kawai", "Fruchterman-Reingold"]:
        physics_options = """{ "physics": { "enabled": false } }"""
    else:
        physics_options = """{"physics": {"forceAtlas2Based": {"gravitationalConstant": -50, "centralGravity": 0.01}, "solver": "forceAtlas2Based"}}"""
    net.set_options(physics_options)
    
    node_to_community = get_greedy_modularity_communities(graph) if layout_option == "Community Detection (Greedy Modularity)" else {}
    pos = get_kamada_kawai_pos(graph) if layout_option == "Kamada-Kawai" else (get_spring_pos(graph) if layout_option == "Fruchterman-Reingold" else {})
    
    predecessors = set(graph.predecessors(selected_node)) if selected_node else set()
    if hide_sources and selected_node:
        predecessors = {p for p in predecessors if graph.in_degree(p) > 0}
    successors = set(graph.successors(selected_node)) if selected_node else set()

    for node in graph.nodes():
        node_kwargs = {'label': node}
        if pos.get(node):
            node_kwargs['x'], node_kwargs['y'] = pos[node][0] * 1000, pos[node][1] * 1000

        if node == selected_node:
            node_kwargs.update({'color': "#ff4d4d", 'size': 25})
        elif node in predecessors:
            node_kwargs.update({'color': "#33cc33", 'size': 20})
        elif node in successors:
            node_kwargs.update({'color': "#ffaa00", 'size': 20})
        else:
            node_kwargs['size'] = 15
            node_kwargs['group'] = node_to_community.get(node) if node_to_community else None
            if not node_kwargs.get('group'):
                node_kwargs['color'] = "#66a3ff"
        net.add_node(node, **node_kwargs)
        
    for source, target, data in graph.edges(data=True):
        edge_kwargs = {'width': 1, 'color': "#888888", 'title': f"Weight: {data.get('weight', 1)}"}
        if selected_node:
            if source == selected_node and target in successors:
                edge_kwargs.update({'color': "#ffaa00", 'width': 3})
            elif target == selected_node and source in predecessors:
                edge_kwargs.update({'color': "#33cc33", 'width': 3})
        net.add_edge(source, target, **edge_kwargs)

    return net

# --- Main App Body ---
st.markdown("### Graph View")
st.write("Click on a node to select it. Use the controls on the left to change the layout or filter the view.")

net_viz = create_interactive_graph(G, selected_node, layout_option, hide_source_neighbors)

try:
    file_path = "interactive_graph.html"
    net_viz.save_graph(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        html_code = f.read()

    final_html = inject_click_handler(html_code)
    components.html(final_html, height=800, scrolling=True)
except Exception as e:
    st.error(f"An error occurred while displaying the graph: {e}")

# --- Instructions and Info ---
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### How to Use")
    st.markdown("""
    - **Select Node:** Click a node in the graph or use the dropdown in the sidebar.
    - **Filter Neighbors:** Toggle the switch to hide highlighted neighbors that are source nodes.
    - **Layouts:** Choose a layout algorithm to rearrange the graph.
    """)
with col2:
    st.markdown("#### Legend")
    st.markdown(f"""
    - <span style='color:{'#ff4d4d'};'>&#9679;</span> **Selected Node**
    - <span style='color:{'#33cc33'};'>&#9679;</span> **Incoming Node**
    - <span style='color:{'#ffaa00'};'>&#9679;</span> **Outgoing Node**
    - **Grouped Colors:** In community detection, nodes of the same color belong to the same community.
    """, unsafe_allow_html=True)