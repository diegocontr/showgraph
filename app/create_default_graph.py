import networkx as nx
from networkx.readwrite import json_graph
import json
import random
import os

# Define the attributes and their generation logic for the default graph.
# This makes it easy to add or remove attributes.
DEFAULT_NODE_ATTRIBUTES = {
    "lines_of_code": lambda: random.randint(20, 600),
    "cyclomatic_complexity": lambda: round(random.uniform(1, 20), 2),
    "function_count": lambda: random.randint(1, 15),
    "class_count": lambda: random.randint(0, 5),
    "docstring": lambda node_name: (f"This is the auto-generated docstring for {node_name}. "
                                  f"It might contain some useful information about the module's purpose.")
                                 if random.random() > 0.3 else "N/A"
}

def create_default_graph(data_folder="../data", filename="large_default_graph.json"):
    """Creates a large default graph JSON file."""
    # Correctly locate the data folder relative to the project root
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    file_path = os.path.join(project_root, data_folder, filename)
    
    print(f"Creating a large default graph file at '{file_path}' (300 nodes)...")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    G_sample = nx.fast_gnp_random_graph(n=300, p=0.015, seed=42, directed=True)
    # Use more descriptive names for nodes, like python files
    mapping = {i: f"module_{i}.py" for i in G_sample.nodes()}
    G_sample = nx.relabel_nodes(G_sample, mapping)

    pos = nx.spring_layout(G_sample, seed=42)

    for node in G_sample.nodes():
         G_sample.nodes[node]['x'] = pos[node][0] * 1500
         G_sample.nodes[node]['y'] = pos[node][1] * 1500
         G_sample.nodes[node]['label'] = node
         # --- Add dummy attributes for demonstration from the defined dictionary ---
         for attr, generator in DEFAULT_NODE_ATTRIBUTES.items():
             # The docstring generator is the only one that needs an argument
             if attr == 'docstring':
                 G_sample.nodes[node][attr] = generator(node)
             else:
                 G_sample.nodes[node][attr] = generator()

    graph_json = json_graph.node_link_data(G_sample)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(graph_json, f, indent=4)
    print(f"Successfully created '{file_path}'.")

if __name__ == "__main__":
    create_default_graph()
