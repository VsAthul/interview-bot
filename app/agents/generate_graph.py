from app.agents.graph import build_graph

compiled_graph = build_graph()
graph_image = compiled_graph.get_graph().draw_mermaid_png()
with open("graph_image.png","wb") as f:
    f.write(graph_image)

