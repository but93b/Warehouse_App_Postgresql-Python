from flask import Flask, render_template, request, redirect
import psycopg2

app = Flask(__name__, template_folder='C:\\Users\\user\\Desktop\\Warehouse\\templates')

# PostgreSQL connection parameters
db_params = {
    'dbname': 'Warehouse',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost',
    'port': '5432'
}

# Function to execute SQL queries
def execute_sql(query, params=None):
    connection = psycopg2.connect(**db_params)
    cursor = connection.cursor()

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # If the query produces a result set, fetch it
        result = cursor.fetchall() if cursor.description else None

        connection.commit()
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        connection.close()

    return result

# Route to show the form for adding/removing products
@app.route('/')
def index():
    return render_template('index.html')

# Route to handle form submission
@app.route('/submit', methods=['POST'])
def submit():
    product_name = request.form['product_name']
    act_type = int(request.form['act_type'])
    amount = int(request.form['amount'])

    # Call the stored procedure
    execute_sql("CALL add_remove_products(%s, %s, %s, CURRENT_TIMESTAMP)", (product_name, act_type, amount))

    return redirect('/')

# Route to handle reset tables
@app.route('/reset-tables', methods=['POST'])
def reset_tables():
    try:
        # Execute SQL queries to drop and create the products table
        execute_sql("DROP TABLE IF EXISTS products;")
        execute_sql("""
            CREATE TABLE products (
                product_id serial PRIMARY KEY,
                product_name VARCHAR(255),
                amount INT
            );
        """)

        # Execute SQL queries to drop and create the products_acts table
        execute_sql("DROP TABLE IF EXISTS products_acts;")
        execute_sql("""
            CREATE TABLE products_acts (
                product_id INT,
                date_time TIMESTAMPTZ,
                act_type INT,
                product_name VARCHAR(255),
                amount INT);
               
        """)
        
        # Создание триггера
        execute_sql("""
            CREATE TRIGGER update_amount_trigger
            AFTER INSERT ON products_acts
            FOR EACH ROW
            EXECUTE FUNCTION update_amount();""") 
        
        # Retrieve data after reset
        products_data = execute_sql("SELECT * FROM products;")
        products_acts_data = execute_sql("SELECT * FROM products_acts;")

        # Return updated data for display
        return render_template('display.html', products=products_data, products_acts=products_acts_data)
    except psycopg2.Error as e:
        return redirect('/')

    
@app.route('/set-functions', methods=['POST'])
def set_functions():
    
        # Execute SQL queries to drop and create the products table
        execute_sql("DROP TABLE IF EXISTS products;")
        execute_sql("""
            CREATE TABLE products (
                product_id serial PRIMARY KEY,
                product_name VARCHAR(255),
                amount INT
            );
        """)

        # Execute SQL queries to drop and create the products_acts table
        execute_sql("DROP TABLE IF EXISTS products_acts;")
        execute_sql("""CREATE TABLE products_acts (
                product_id INT,
                date_time TIMESTAMPTZ,
                act_type INT,
                product_name VARCHAR(255),
                amount INT);
               
        """)
        
        # Создание процедуры add_remove_products
        execute_sql("""CREATE OR REPLACE PROCEDURE add_remove_products(     
                    p_product_name VARCHAR(255),     
                    p_act_type INT,     
                    p_amount INT, 
                    p_date_time TIMESTAMPTZ) 
                    AS $$ 

                    DECLARE
                        v_product_id INT;
                    BEGIN
                            -- Проверяем, введено ли число товара 
                        IF p_amount <= 0 THEN 
                            PERFORM pg_sleep(1);  
                            PERFORM pg_notify('flash_message', 'Не введено количество товара'); 
                            RETURN;
                            -- Проверяем, есть ли товар в наличии перед списанием 
                        ELSIF p_act_type = 1 AND (SELECT amount FROM products WHERE product_name = p_product_name) < p_amount THEN 
                            PERFORM pg_sleep(1); 
                            PERFORM pg_notify('flash_message', 'Недостаточно товара для списания'); 
                            RETURN; 
                            -- Проверяем, существует ли товар в таблице products
                        ELSEIF p_act_type = 1 AND NOT EXISTS (SELECT 1 FROM products WHERE product_name = p_product_name) THEN
                            PERFORM pg_sleep(1); 
                            PERFORM pg_notify('flash_message', 'Нет такого товара');
                            RETURN;  
                        ELSE
                            -- Добавляем запись в таблицу products_acts
                                INSERT INTO products_acts (product_name, date_time, act_type, amount)
                                VALUES (p_product_name, p_date_time, p_act_type, p_amount);   
                            PERFORM pg_sleep(1); 
                            
                            -- Получаем id продукта
                            SELECT product_id INTO v_product_id FROM products WHERE product_name = p_product_name;
                        
                            -- Обновляем запись в таблице products_acts, где date_time = p_date_time
                            UPDATE products_acts
                            SET product_id = v_product_id
                            WHERE date_time = p_date_time;
                        END IF;

                    END;

                    $$ LANGUAGE plpgsql;
                    """)
        
        # Создание триггерной функции update_amount()
        execute_sql("""CREATE OR REPLACE FUNCTION update_amount() RETURNS TRIGGER AS $$ 
                        BEGIN
                            -- Если это добавление товара, увеличиваем количество
                            IF NEW.act_type = 0 THEN
                                UPDATE products SET amount = amount + NEW.amount WHERE product_name = NEW.product_name;
                                
                                -- Если товар с таким названием отсутствует, добавляем его в таблицу products
                                IF NOT FOUND THEN
                                    INSERT INTO products (product_name, amount) VALUES (NEW.product_name, NEW.amount);
                                END IF;
                            ELSIF NEW.act_type = 1 THEN
                                -- Если это списание товара, уменьшаем количество
                                UPDATE products SET amount = amount - NEW.amount WHERE product_name = NEW.product_name;
                                
                            END IF;

                            RETURN NEW;
                        END;

                        $$ LANGUAGE plpgsql;
                    """)
        
        # Создание триггера
        execute_sql("""
            CREATE TRIGGER update_amount_trigger
            AFTER INSERT ON products_acts
            FOR EACH ROW
            EXECUTE FUNCTION update_amount();""") 
        
        
        return redirect('/')
    
# Route to display the products and products_acts tables
@app.route('/display')
def display():
    # Retrieve data from the tables
    products_data = execute_sql("SELECT * FROM products;")
    products_acts_data = execute_sql("SELECT * FROM products_acts;")

    return render_template('display.html', products=products_data,
                           products_acts=products_acts_data)
if __name__ == '__main__':
    app.run(debug=True)