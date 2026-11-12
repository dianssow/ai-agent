CREATE EXTENSION IF NOT EXISTS vector;

-- Clean reset
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;

select * from products;

-- Categories table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE NOT NULL
);

-- Products table with Foreign Key + Hybrid Search Vector
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category_id INT NOT NULL REFERENCES categories(category_id) ON DELETE RESTRICT,
    price NUMERIC(10, 2) NOT NULL,
    stock_quantity INT NOT NULL CHECK (stock_quantity >= 0),
    description TEXT NOT NULL,
    embedding VECTOR(768)
);

-- 3. Orders & Audit Logs tables
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(product_id),
    quantity INT NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    log_id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger: Auto-decrement stock and log low-stock warnings
CREATE OR REPLACE FUNCTION update_stock_on_order()
RETURNS TRIGGER AS $$
DECLARE
    remaining_stock INT;
BEGIN
    UPDATE products
    SET stock_quantity = stock_quantity - NEW.quantity
    WHERE product_id = NEW.product_id
    RETURNING stock_quantity INTO remaining_stock;

    IF remaining_stock < 5 THEN
        INSERT INTO audit_logs (event_type, message)
        VALUES ('LOW_STOCK', 'Product ID ' || NEW.product_id || ' is low on stock (' || remaining_stock || ' left).');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_after_order_insert
AFTER INSERT ON orders
FOR EACH ROW
EXECUTE FUNCTION update_stock_on_order();

-- Seed Categories & Products (embeddings will be populated by ingest_products.py)
INSERT INTO categories (category_name) VALUES
    ('Networking'),
    ('Computing'),
    ('Accessories');

INSERT INTO products (product_name, category_id, price, stock_quantity, description) VALUES
   (
    'CloudBox Pro v2',
    1,
    149.99,
    12,
    'Enterprise-WLAN-6-Router und -Gateway. Zum Zurücksetzen halten Sie die Reset-Taste auf der Rückseite 10 Sekunden lang gedrückt, bis die LED orange blinkt. Eine dauerhaft rot leuchtende Power-LED weist auf ein Überspannungsproblem hin: Ziehen Sie den Netzstecker für 2 Minuten und schließen Sie das Gerät direkt an eine Wandsteckdose an. Der Fehler ERR-904B bedeutet, dass das lokale TLS-Zertifikat abgelaufen ist; führen Sie cloudbox-cli --renew-cert per SSH aus.'
),
(
    'MeshNode Mini',
    1,
    69.99,
    0,
    'Kompakter WLAN-6-Mesh-Repeater zur Beseitigung von Funklöchern in Wohnungen und kleinen Büros. Einfache Einrichtung über die mobile App.'
),
(
    'NetShield Router X1',
    1,
    129.00,
    8,
    'Sicherer Dualband-Gigabit-Router mit integrierter Firewall und VPN-Unterstützung. Ideale Alternative für das Homeoffice und kleine Unternehmen.'
),
(
    'DevBook 14 Linux Edition',
    2,
    1199.00,
    4,
    '14-Zoll-Entwickler-Laptop mit vorinstalliertem Ubuntu LTS, 32 GB RAM, 1 TB NVMe-SSD, mattem entspiegeltem Display und 12 Stunden Akkulaufzeit für rechenintensive Kompilierungen und Docker-Workloads.'
),
(
    'ErgoMech Wireless Keyboard',
    3,
    139.50,
    20,
    'Geteilte ergonomische mechanische Tastatur mit leisen taktilen Schaltern, über USB-C aufladbarem Akku und Multi-Device-Bluetooth-Kopplung für Programmierer.'
);

