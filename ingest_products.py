import ollama
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432",
}

EMBEDDING_MODEL = "nomic-embed-text"


def generate_product_embeddings():
  conn = None
  try:
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    register_vector(conn)
    cursor = conn.cursor()

    cursor.execute("""
            SELECT p.product_id, p.product_name, c.category_name, p.description
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            ORDER BY p.product_id;
        """)
    products = cursor.fetchall()
    print(
        f"[INFO] Found {len(products)} products to vectorize."
    )

    for product in products:
      # Combine name, category, and description for richer semantic retrieval
      rich_text = (
          f"{product['product_name']} ({product['category_name']}): "
          f"{product['description']}"
      )
      print(
          f"[INFO] Embedding product #{product['product_id']}:"
          f" {product['product_name']}..."
      )

      response = ollama.embeddings(
          model=EMBEDDING_MODEL, prompt=f"search_document: {rich_text}"
      )
      vector = response["embedding"]

      cursor.execute(
          "UPDATE products SET embedding = %s WHERE product_id = %s;",
          (vector, product["product_id"]),
      )

    conn.commit()
    print("[SUCCESS] All product embeddings updated successfully.")

  except Exception as e:
    if conn:
      conn.rollback()
    print(f"[ERROR] Product embedding ingestion failed: {e}")
  finally:
    if conn:
      cursor.close()
      conn.close()


if __name__ == "__main__":
  generate_product_embeddings()
