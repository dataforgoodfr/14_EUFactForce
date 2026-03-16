import random

from .colors import AppColors


class RandomGraphGenerator:
    def __init__(self):
        self.n_min_paper_nodes = 5
        self.n_max_paper_nodes = 10
        self.nodes_paper = [
            {"data": {"id": f"node_paper_{i}", "label": f"Paper {i}", "type": "paper"}}
            for i in range(self.n_max_paper_nodes)
        ]
        self.nodes_journal = [
            {"data": {"id": "node_journal_0", "label": "Journal A", "type": "journal"}},
            {"data": {"id": "node_journal_1", "label": "Journal B", "type": "journal"}},
            {"data": {"id": "node_journal_2", "label": "Journal C", "type": "journal"}},
        ]
        self.stylesheet = [
            {
                "selector": "node",
                "style": {
                    "label": "data(label)",
                    "text-valign": "center",
                    "color": "black",
                },
            },
            {
                "selector": 'node[type="paper"]',
                "style": {
                    "background-color": AppColors.blue,
                },
            },
            {
                "selector": 'node[type="journal"]',
                "style": {
                    "background-color": AppColors.green,
                },
            },
            {
                "selector": "edge",
                "style": {
                    "width": 2,
                    "line-color": "black",
                },
            },
        ]

    def get_graph_data(self):
        nodes = random.sample(
            self.nodes_paper,
            random.randint(self.n_min_paper_nodes, self.n_max_paper_nodes),
        )
        edges = []
        for source_node in nodes:
            target_node = random.sample(self.nodes_journal, 1)[0]
            edges.append(
                {
                    "data": {
                        "source": source_node["data"]["id"],
                        "target": target_node["data"]["id"],
                    }
                }
            )
        return nodes + self.nodes_journal + edges
