"""Neo4j async client — entity/relationship upsert and graph traversal."""
from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self) -> None:
        await self._driver.close()

    async def health_check(self) -> bool:
        try:
            async with self._driver.session() as session:
                await session.run("RETURN 1")
            return True
        except Exception:
            return False

    async def upsert_entities(self, entities: list[str], document_id: str) -> None:
        """Create or update Entity nodes and link them to a document."""
        async with self._driver.session() as session:
            await session.run(
                """
                UNWIND $entities AS name
                MERGE (e:Entity {name: name})
                WITH e
                MATCH (d:Document {id: $document_id})
                MERGE (d)-[:CONTAINS]->(e)
                """,
                entities=entities,
                document_id=document_id,
            )

    async def upsert_document(self, document_id: str, name: str) -> None:
        """Create or update a Document node."""
        async with self._driver.session() as session:
            await session.run(
                "MERGE (d:Document {id: $id}) SET d.name = $name",
                id=document_id,
                name=name,
            )

    async def upsert_relationships(self, relationships: list[dict]) -> None:
        """Create entity-to-entity relationships."""
        async with self._driver.session() as session:
            for rel in relationships:
                src, rel_type, dst = rel["src"], rel["rel"], rel["dst"]
                await session.run(
                    f"""
                    MERGE (a:Entity {{name: $src}})
                    MERGE (b:Entity {{name: $dst}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    """,
                    src=src,
                    dst=dst,
                )

    async def traverse(
        self,
        entity_names: list[str],
        depth: int = 2,
    ) -> tuple[list[str], list[str]]:
        """BFS traversal from seed entities up to given depth.

        Returns (connected_entity_names, graph_path_strings).
        """
        if not entity_names:
            return [], []

        async with self._driver.session() as session:
            result = await session.run(
                """
                UNWIND $names AS name
                MATCH (start:Entity {name: name})
                CALL apoc.path.subgraphAll(start, {maxLevel: $depth})
                YIELD nodes, relationships
                UNWIND nodes AS node
                RETURN DISTINCT node.name AS entity_name
                """,
                names=entity_names,
                depth=depth,
            )
            records = await result.values()
            connected = [r[0] for r in records if r[0]]

            # Build readable path strings
            path_result = await session.run(
                """
                UNWIND $names AS name
                MATCH (a:Entity {name: name})-[r]->(b:Entity)
                RETURN a.name AS src, type(r) AS rel, b.name AS dst
                LIMIT 20
                """,
                names=entity_names,
            )
            paths_data = await path_result.values()
            paths = [f"{row[0]} --{row[1]}--> {row[2]}" for row in paths_data]

        return connected, paths

    async def get_entity_subgraph(self, entity_name: str) -> dict[str, Any]:
        """Return subgraph JSON for visualization ({nodes, edges})."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {name: $name})-[r]->(b:Entity)
                RETURN a.name AS src, type(r) AS rel, b.name AS dst
                LIMIT 50
                """,
                name=entity_name,
            )
            records = await result.values()

        nodes = set()
        edges = []
        for src, rel, dst in records:
            nodes.add(src)
            nodes.add(dst)
            edges.append({"src": src, "rel": rel, "dst": dst})

        return {"nodes": list(nodes), "edges": edges, "entity": entity_name}
