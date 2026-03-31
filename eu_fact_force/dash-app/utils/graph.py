import random
import json

from .colors import EUPHAColors

stylesheet = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "text-valign": "center",
            "color": "black",
            "font-size": 10,
        },
    },
    {
        "selector": 'node[type="chunk"]',
        "style": {
            "background-color": EUPHAColors.light_green,
        },
    },
    {
        "selector": 'node[type="document"]',
        "style": {
            "background-color": EUPHAColors.orange,
        },
    },
    {
        "selector": 'node[type="author"]',
        "style": {
            "background-color": EUPHAColors.light_blue,
        },
    },
    {
        "selector": 'node[type="journal"]',
        "style": {
            "background-color": EUPHAColors.dark_blue,
        },
    },
    {
        "selector": 'node[type="keyword"]',
        "style": {
            "background-color": EUPHAColors.dark_green,
        },
    },
    {
        "selector": "edge",
        "style": {
            "width": 1,
            "line-color": "black",
        },
    },
]


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
        self.stylesheet = stylesheet

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


class TestGraph:
    def __init__(self):
        self.load_search_results()
        self.stylesheet = stylesheet

    def load_search_results(self):
        with open("data/search_results.json", "r") as f:
            self.search_results = json.load(f)

    def transform(self):
        nodes = {}
        edges = []
        filters = {
            "chunk_types": [],
            "documents": [],
            "journal": [],
            "keywords": [],
            "authors": [],
            "date": [],
        }

        # chunks
        for i, chunk in enumerate(self.search_results["chunks"]):
            chunk_id = f"chunk_{i}"
            filters["chunk_types"].append(chunk["type"])
            nodes[chunk_id] = {
                "data": {
                    "id": chunk_id,
                    "label": chunk_id,
                    "type": "chunk",
                    "metadata": chunk,
                }
            }
            # documents
            document_id = chunk["metadata"]["document_id"]
            document_metadata = self.search_results["documents"][document_id]
            filters["documents"].append(document_id)
            filters["date"].append(document_metadata["date"])
            if document_id not in nodes:
                nodes[document_id] = {
                    "data": {
                        "id": document_id,
                        "label": document_metadata["title"],
                        "type": "document",
                        "metadata": document_metadata,
                    }
                }
            edges.append(
                {
                    "data": {
                        "source": chunk_id,
                        "target": document_id,
                    }
                }
            )
            # journal and authors
            journal_id = f"journal_{document_metadata['journal']}"
            filters["journal"].append(journal_id)
            if journal_id not in nodes:
                nodes[journal_id] = {
                    "data": {
                        "id": journal_id,
                        "label": document_metadata["journal"],
                        "type": "journal",
                    }
                }
            edges.append(
                {
                    "data": {
                        "source": document_id,
                        "target": journal_id,
                    }
                }
            )
            for author in document_metadata["authors"]:
                author_id = f"author_{author}"
                filters["authors"].append(author_id)
                if author_id not in nodes:
                    nodes[author_id] = {
                        "data": {"id": author_id, "label": author, "type": "author"}
                    }
                edges.append(
                    {
                        "data": {
                            "source": document_id,
                            "target": author_id,
                        }
                    }
                )

            # keywords
            for keyword in chunk["metadata"]["keywords"]:
                keyword_id = f"keyword_{keyword}"
                filters["keywords"].append(keyword_id)
                if keyword_id not in nodes:
                    nodes[keyword_id] = {
                        "data": {"id": keyword_id, "label": keyword, "type": "keyword"}
                    }
                edges.append(
                    {
                        "data": {
                            "source": chunk_id,
                            "target": keyword_id,
                        }
                    }
                )

        return nodes, edges, filters
