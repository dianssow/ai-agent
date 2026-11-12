import ollama
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from mcp.server.mcpserver import MCPServer
from config import DB_CONFIG, DISTANCE_THRESHOLD, EMBEDDING_MODEL, LLM_MODEL
mcp = MCPServer("Catalog, Support & Order MCP Server")




def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    register_vector(conn)
    return conn


@mcp.tool()
def search_products_hybrid(query: str, top_k: int = 3) -> str:
    """
    Search products by natural language description, use-case, technical issue, or error code
    (e.g., 'laptop for docker', 'red LED issue', 'ERR-904B').
    Combines semantic vector search and keyword search (RRF) on product descriptions.
    """
    try:
        response = ollama.embeddings(
            model=EMBEDDING_MODEL, prompt=f"search_query: {query}"
        )
        query_vector = response["embedding"]

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            WITH semantic_search AS (
                SELECT p.product_id,
                       ROW_NUMBER() OVER (ORDER BY p.embedding <=> %s::vector) AS rank
                FROM products p
                WHERE p.embedding IS NOT NULL
                  AND (p.embedding <=> %s::vector) < %s
                LIMIT 10
            ),
            keyword_search AS (
                SELECT p.product_id,
                       ROW_NUMBER() OVER (
                           ORDER BY ts_rank(
                               to_tsvector('english', p.product_name || ' ' || p.description),
                               websearch_to_tsquery('english', %s)
                           ) DESC
                       ) AS rank
                FROM products p
                WHERE to_tsvector('english', p.product_name || ' ' || p.description)
                      @@ websearch_to_tsquery('english', %s)
                LIMIT 10
            ),
            rrf_scores AS (
                SELECT
                    COALESCE(s.product_id, k.product_id) AS product_id,
                    COALESCE(1.0 / (60 + s.rank), 0.0) + COALESCE(1.0 / (60 + k.rank), 0.0) AS score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.product_id = k.product_id
            )
            SELECT p.product_id, p.product_name, c.category_name, p.price, p.stock_quantity, p.description, r.score
            FROM rrf_scores r
            JOIN products p ON p.product_id = r.product_id
            JOIN categories c ON p.category_id = c.category_id
            ORDER BY r.score DESC
            LIMIT %s;
        """
        cursor.execute(
            sql,
            (query_vector, query_vector, DISTANCE_THRESHOLD, query, query, top_k),
        )
        matches = cursor.fetchall()
        cursor.close()
        conn.close()

        if not matches:
            return "No matching products or troubleshooting info found in the catalog."

        results = []
        for m in matches:
            results.append(
                f"- [ID #{m['product_id']}] {m['product_name']} (Category: {m['category_name']}) | "
                f"Price: ${m['price']} | Stock: {m['stock_quantity']} | RRF Score: {m['score']:.4f}\n"
                f"  Details: {m['description']}"
            )
        return "\n".join(results)
    except Exception as e:
        return f"Hybrid search error: {str(e)}"


@mcp.tool()
def get_product_by_name(product_name: str) -> str:
    """Fetch exact stock, price, and category for a product using its name (case-insensitive partial match)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.product_id, p.product_name, c.category_name, p.price, p.stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.product_name ILIKE %s;
            """,
            (f"%{product_name}%",),
        )
        products = cursor.fetchall()
        cursor.close()
        conn.close()

        if not products:
            return f"No product found matching '{product_name}'."

        return "\n".join([
            f"- [ID #{p['product_id']}] {p['product_name']} ({p['category_name']}) - "
            f"Price: ${p['price']} | Stock: {p['stock_quantity']} units"
            for p in products
        ])
    except Exception as e:
        return f"Error searching product by name: {str(e)}"


@mcp.tool()
def get_products_by_category(category_name: str) -> str:
    """List all in-stock products belonging to a specific category (e.g., 'Networking', 'Computing', 'Accessories')."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.product_id, p.product_name, c.category_name, p.price, p.stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE LOWER(c.category_name) = LOWER(%s) AND p.stock_quantity > 0;
            """,
            (category_name,),
        )
        products = cursor.fetchall()
        cursor.close()
        conn.close()

        if not products:
            return f"No in-stock products found in category '{category_name}'."

        return f"In-stock products in '{category_name}':\n" + "\n".join([
            f"- [ID #{p['product_id']}] {p['product_name']} - ${p['price']} (Stock: {p['stock_quantity']})"
            for p in products
        ])
    except Exception as e:
        return f"Error fetching products by category: {str(e)}"


@mcp.tool()
def get_all_products() -> str:
    """List all products currently available in stock across all categories."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.product_id, p.product_name, c.category_name, p.price, p.stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.stock_quantity > 0
            ORDER BY c.category_name, p.product_name;
        """)
        products = cursor.fetchall()
        cursor.close()
        conn.close()

        if not products:
            return "No products currently available in stock."

        return "Available catalog:\n" + "\n".join([
            f"- [ID #{p['product_id']}] {p['product_name']} [{p['category_name']}] - "
            f"${p['price']} (Stock: {p['stock_quantity']})"
            for p in products
        ])
    except Exception as e:
        return f"Error listing products: {str(e)}"


@mcp.tool()
def get_alternative_product(excluded_product_id: int) -> str:
    """Find an in-stock alternative product in the same category when a product is out of stock."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.product_id, p.product_name, c.category_name, p.price, p.stock_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            WHERE p.category_id = (SELECT category_id FROM products WHERE product_id = %s)
              AND p.product_id != %s
              AND p.stock_quantity > 0
            LIMIT 1;
            """,
            (excluded_product_id, excluded_product_id),
        )
        alt = cursor.fetchone()
        cursor.close()
        conn.close()

        if not alt:
            return "No alternative in-stock product found in this category."

        return (
            f"Alternative available: [ID #{alt['product_id']}] {alt['product_name']} "
            f"({alt['category_name']}) - Price: ${alt['price']} | Stock: {alt['stock_quantity']} units"
        )
    except Exception as e:
        return f"Alternative product search failed: {str(e)}"


@mcp.tool()
def place_order(product_id: int, quantity: int, confirmed: bool = False) -> str:
    """
    Place a customer order.
    IMPORTANT: Set confirmed=True ONLY AFTER the user has explicitly replied 'yes' or confirmed a summary.
    On the first order request, ALWAYS call with confirmed=False to generate a confirmation prompt.
    """
    if not confirmed:
        return (
        "CONFIRMATION REQUIRED: Do not execute yet. Ask the user to explicitly"
        f" confirm ordering {quantity}x Product ID #{product_id} before"
        " calling place_order with confirmed=True."
    )
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT product_name, stock_quantity FROM products WHERE product_id = %s;",
            (product_id,),
        )
        product = cursor.fetchone()
        if not product:
            cursor.close()
            conn.close()
            return f"Error: Product ID {product_id} does not exist."

        if product["stock_quantity"] < quantity:
            cursor.close()
            conn.close()
            return (
                f"Order rejected: Insufficient stock for '{product['product_name']}' "
                f"(Requested: {quantity}, Available: {product['stock_quantity']})."
            )

        cursor.execute(
            "INSERT INTO orders (product_id, quantity) VALUES (%s, %s) RETURNING order_id;",
            (product_id, quantity),
        )
        order_id = cursor.fetchone()["order_id"]
        conn.commit()
        cursor.close()
        conn.close()

        return (
            f"Order confirmed: Order #{order_id} placed for {quantity}x "
            f"'{product['product_name']}' (ID #{product_id})."
        )
    except Exception as e:
        return f"Order placement failed: {str(e)}"


@mcp.tool()
def get_audit_logs() -> str:
    """Fetch the 5 most recent system audit logs and low-stock warnings."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT log_id, event_type, message, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 5;"
        )
        logs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not logs:
            return "No audit logs found."

        return "\n".join(
            [f"[{l['created_at']}] {l['event_type']}: {l['message']}" for l in logs]
        )
    except Exception as e:
        return f"Failed to fetch audit logs: {str(e)}"


if __name__ == "__main__":
    mcp.run()
