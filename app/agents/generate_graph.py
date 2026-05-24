from app.agents.graph import build_report_graph

compiled_graph = build_report_graph()
graph_image = compiled_graph.get_graph().draw_mermaid_png()
with open("graph_image3.png","wb") as f:
    f.write(graph_image)

