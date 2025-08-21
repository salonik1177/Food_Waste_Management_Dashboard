import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import os
from st_aggrid import AgGrid, GridOptionsBuilder

# ---------- Database ----------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "food_waste.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
def get_connection():
   
    # Food listings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_listings(
            Food_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Food_Name TEXT,
            Quantity INTEGER,
            Expiry_Date TEXT,
            Provider_ID INTEGER,
            Provider_Type TEXT,
            Location TEXT,
            Food_Type TEXT,
            Meal_Type TEXT
        )
    """)
    # Contacts
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts(
            Contact_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            Role TEXT,
            Organization TEXT,
            Email TEXT,
            Phone TEXT,
            City TEXT,
            Notes TEXT
        )
    """)

    return conn

def run_write(query, params=()):
    conn = get_connection()
    conn.execute(query, params)
    conn.commit()

def load_df(query, params=()):
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


# ---------- App Config ----------
st.set_page_config(page_title="Local Food Wastage System",
                   layout="wide",
                   initial_sidebar_state="expanded")


# ---------- Sidebar with Logo ----------
st.sidebar.image(
    "https://img.icons8.com/fluency/96/meal.png",
    use_container_width=True
)

st.sidebar.markdown(
    "<h3 style='text-align: center; color: white;'>🥗Food Wastage System</h3>",
    unsafe_allow_html=True
)

st.sidebar.markdown("---")


# Sidebar Navigation
page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Analytics", "Providers & Receivers", "CRUD Operations", "Contacts", "Queries & Reports", "Settings / About"]
)


# ---------- 1. Dashboard ----------
if page == "Dashboard":
    st.title("📊 Local Food Wastage Management ")
    st.markdown("### Interactive overview of food listings, providers, and receivers")

    df = load_df("SELECT * FROM food_listings")

    if not df.empty:
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("🍽️ Total Listings", len(df))
        with col2: st.metric("📦 Total Quantity", int(df["Quantity"].sum()))
        with col3: st.metric("🏢 Unique Providers", df["Provider_ID"].nunique())
        with col4: st.metric("🌍 Cities Covered", df["Location"].nunique())

        st.divider()

        # Filters
        with st.expander("🔍 Filters", expanded=False):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                city_filter = st.multiselect("Filter by City", df["Location"].unique())
            with f_col2:
                type_filter = st.multiselect("Filter by Food Type", df["Food_Type"].unique())
            with f_col3:
                provider_filter = st.multiselect("Filter by Provider Type", df["Provider_Type"].unique())

            if city_filter: df = df[df["Location"].isin(city_filter)]
            if type_filter: df = df[df["Food_Type"].isin(type_filter)]
            if provider_filter: df = df[df["Provider_Type"].isin(provider_filter)]

        st.divider()

            # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(df, names="Food_Type", values="Quantity",
                                   title="🍴 Distribution by Food Type"), use_container_width=True)
        with c2:
            st.plotly_chart(px.bar(df, x="Expiry_Date", y="Quantity", color="Food_Type",
                                         title="📆 Quantity by Expiry Date", barmode="stack"),
                            use_container_width=True)

        st.divider()
        st.subheader("📋 Food Listings Data")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("⚠️ No food listings available. Please add some records first.")


# ---------- 2. Analytics ----------
elif page == "Analytics":
    st.title("📈 Analytics & Insights")
    df = load_df("SELECT * FROM food_listings")
    if not df.empty:
        tab1, tab2, tab3 = st.tabs(["Food Trends", "Expiry Trends", "Provider Analysis"])
        with tab1:
            st.bar_chart(df.groupby("Food_Type")["Quantity"].sum())
        with tab2:
            st.line_chart(df.groupby("Expiry_Date")["Quantity"].sum())
        with tab3:
            st.bar_chart(df.groupby("Provider_Type")["Quantity"].sum())
    else:
        st.info("No data available for analytics.")


# ---------- 3. Providers & Receivers ----------
elif page == "Providers & Receivers":
    st.title("🏢 Providers & Receivers Directory")

    choice = st.radio("View directory for:", ["Providers", "Receivers"], horizontal=True)
    conn = get_connection()

    # ---------- Providers ----------
    if choice == "Providers":
        cities_df = load_df("SELECT DISTINCT Location AS City FROM food_listings ORDER BY City")
        cities = ["All"] + cities_df["City"].dropna().tolist()
        city = st.selectbox("Select a City", cities)

        if city == "All":
            q = """
                SELECT 
                    Provider_ID,
                    Provider_Type,
                    Location AS City,
                    COUNT(Food_ID)   AS Total_Listings,
                    SUM(Quantity)    AS Total_Quantity
                FROM food_listings
                GROUP BY Provider_ID, Provider_Type, Location
                ORDER BY Total_Quantity DESC
            """
            df_prov = load_df(q)
        else:
            q = """
                SELECT 
                    Provider_ID,
                    Provider_Type,
                    Location AS City,
                    COUNT(Food_ID)   AS Total_Listings,
                    SUM(Quantity)    AS Total_Quantity
                FROM food_listings
                WHERE Location = ?
                GROUP BY Provider_ID, Provider_Type, Location
                ORDER BY Total_Quantity DESC
            """
            df_prov = load_df(q, (city,))

        st.subheader(f"📋 Providers in {city if city != 'All' else 'All Cities'}")
        if not df_prov.empty:
            st.dataframe(df_prov, use_container_width=True)


    # ---------- Receivers ----------
    else:
        # helper: check tables exist
        def table_exists(name: str) -> bool:
            return conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (name,)
            ).fetchone() is not None

        if not (table_exists("receivers") and table_exists("claims")):
            st.warning("Receivers/Claims tables not found in the database.")
        else:
            cities_df = load_df("SELECT DISTINCT City FROM receivers ORDER BY City")
            cities = ["All"] + cities_df["City"].dropna().tolist()
            city = st.selectbox("Select a City", cities)

            base = """
                SELECT 
                    r.Receiver_ID,
                    r.Name AS Receiver_Name,
                    r.Type AS Receiver_Type,
                    r.City,
                    COUNT(cl.Claim_ID) AS Total_Claims
                FROM receivers r
                LEFT JOIN claims cl ON r.Receiver_ID = cl.Receiver_ID
                {where}
                GROUP BY r.Receiver_ID, r.Name, r.Type, r.City
                ORDER BY Total_Claims DESC
            """
            if city == "All":
                df_recv = load_df(base.format(where=""))
            else:
                df_recv = load_df(base.format(where="WHERE r.City = ?"), (city,))

            st.subheader(f"📋 Receivers in {city if city != 'All' else 'All Cities'}")
            if not df_recv.empty:
                st.dataframe(df_recv, use_container_width=True)
            else:
                st.info("No receivers found for this city.")


# ---------- 4. CRUD Operations ----------
elif page == "CRUD Operations":
    st.title("✍️ Manage Food Listings")
    conn = get_connection()

    # Create
    st.subheader("➕ Add New Listing")
    with st.form("create_listing_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Food Name")
            qty = st.number_input("Quantity", min_value=1)
        with col2:
            provider_id = st.number_input("Provider ID", min_value=1)
            provider_type = st.text_input("Provider Type")
        with col3:
            city = st.text_input("City")
            food_type = st.text_input("Food Type")
            meal_type = st.text_input("Meal Type")
        expiry = st.date_input("Expiry Date", datetime.today())
        add = st.form_submit_button("Add Listing")
        if add:
            run_write("""INSERT INTO food_listings 
                        (Food_Name, Quantity, Expiry_Date, Provider_ID, Provider_Type, Location, Food_Type, Meal_Type) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (name, qty, expiry.strftime("%Y-%m-%d"), provider_id, provider_type, city, food_type, meal_type))
            st.success("✅ New listing added!")

    # Read
    st.subheader("📋 Current Listings")
    listings = conn.execute("SELECT * FROM food_listings").fetchall()
    if listings:
        df = pd.DataFrame(listings, columns=["Food_ID", "Food_Name", "Quantity", "Expiry_Date", 
                                             "Provider_ID", "Provider_Type", "Location", "Food_Type", "Meal_Type"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No listings available.")

    # Update
    st.subheader("✏️ Update Listing")
    update_options = ["None"] + [f"{row[0]} - {row[1]}" for row in listings]
    update_choice = st.selectbox("Select Listing to update", update_options)
    if update_choice != "None":
        update_id = int(update_choice.split(" - ")[0])
        new_qty = st.number_input("New Quantity", min_value=1, key="upd_qty")
        new_city = st.text_input("New City (leave blank if no change)", key="upd_city")
        if st.button("Update Listing"):
            if new_city:
                run_write("UPDATE food_listings SET Quantity=?, Location=? WHERE Food_ID=?", 
                          (new_qty, new_city, update_id))
            else:
                run_write("UPDATE food_listings SET Quantity=? WHERE Food_ID=?", (new_qty, update_id))
            st.success(f"✅ Listing {update_id} updated!")

    # Delete
    st.subheader("🗑️ Delete Listing")
    delete_options = ["None"] + [f"{row[0]} - {row[1]}" for row in listings]
    delete_choice = st.selectbox("Select Listing to delete", delete_options)
    if delete_choice != "None":
        del_id = int(delete_choice.split(" - ")[0])
        if st.button("Delete Listing"):
            run_write("DELETE FROM food_listings WHERE Food_ID=?", (del_id,))
            st.success(f"🗑️ Listing {del_id} deleted!")

# ---------- 5 CONTACTS ----------
elif page == "Contacts":
    st.title("📞 Contact Information")
    conn = get_connection()
    tab = st.radio("View Contacts for", ["Providers", "Receivers"])

    if tab == "Providers":
        df = pd.read_sql("SELECT Name, City, Contact FROM providers", conn)
    else:
        df = pd.read_sql("SELECT Name, City, Contact FROM receivers", conn)

    st.dataframe(df)
elif page == "Claims":
    st.title("📦 Manage Claims")
    conn = get_connection()

  


# ---------- 6. Queries & Reports ----------
elif page == "Queries & Reports":
    st.title("📑 SQL Queries & Reports")

    # Dropdown for queries
    query_options = {
        # 1. Number of food providers in each city
        "Number of food providers in each city": """
            SELECT City, COUNT(*) AS total_providers
            FROM providers
            GROUP BY City
            ORDER BY total_providers DESC
        """,

        # 2. Number of receivers in each city
        "Number of receivers in each city": """
            SELECT City, COUNT(*) AS total_receivers
            FROM receivers
            GROUP BY City
            ORDER BY total_receivers DESC
        """,

        # 3. Provider type contributing the most food
        "Provider type contributing the most food": """
            SELECT Provider_Type, SUM(Quantity) AS total_quantity
            FROM food_listings
            GROUP BY Provider_Type
            ORDER BY total_quantity DESC
        """,

        # 4. Contact info of providers in a specific city
        "Contact info of providers in a specific city": """
            SELECT Name, City, Contact
            FROM providers
            WHERE City = 'New Jessica'   -- change dynamically if needed
        """,

        # 5. Receivers who have claimed the most food
        "Receivers who have claimed the most food": """
            SELECT r.Name, r.City, COUNT(c.Claim_ID) AS total_claims
            FROM receivers r
            LEFT JOIN claims c ON r.Receiver_ID = c.Receiver_ID
            GROUP BY r.Name, r.City
            ORDER BY total_claims DESC
            LIMIT 10
        """,

        # 6. Total quantity of food available
        "Total quantity of food available": """
            SELECT SUM(Quantity) AS total_quantity
            FROM food_listings
        """,

        # 7. City with the highest number of food listings
        "City with the highest number of food listings": """
            SELECT p.City, COUNT(f.Food_ID) AS total_listings
            FROM food_listings f
            JOIN providers p ON f.Provider_ID = p.Provider_ID
            GROUP BY p.City
            ORDER BY total_listings DESC
            LIMIT 1;
        """,

        # 8. Most commonly available food types
        "Most commonly available food types": """
            SELECT Food_Type, COUNT(*) AS count_foods
            FROM food_listings
            GROUP BY Food_Type
            ORDER BY count_foods DESC
        """,

        # 9. Number of claims for each food item
        "Number of claims for each food item": """
            SELECT f.Food_ID, f.Food_Type, COUNT(c.Claim_ID) AS total_claims
            FROM food_listings f
            LEFT JOIN claims c ON f.Food_ID = c.Food_ID
            GROUP BY f.Food_ID, f.Food_Type
            ORDER BY total_claims DESC
        """,

        # 10. Provider with highest successful claims
        "Provider with highest successful claims": """
            SELECT p.Name, COUNT(c.Claim_ID) AS successful_claims
            FROM providers p
            JOIN food_listings f ON p.Provider_ID = f.Provider_ID
            JOIN claims c ON f.Food_ID = c.Food_ID
            WHERE c.Status = 'Successful'
            GROUP BY p.Name
            ORDER BY successful_claims DESC
            LIMIT 1
        """,

        # 11. Percentage of claims by status
        "Percentage of claims by status": """
            SELECT Status, 
                   ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM claims)), 2) AS percentage
            FROM claims
            GROUP BY Status
        """,

        # 12. Average quantity of food claimed per receiver
        "Average quantity of food claimed per receiver": """
            SELECT r.Name, AVG(f.Quantity) AS avg_claimed_quantity
            FROM receivers r
            JOIN claims c ON r.Receiver_ID = c.Receiver_ID
            JOIN food_listings f ON c.Food_ID = f.Food_ID
            GROUP BY r.Name
        """,

        # 13. Most claimed meal type
        "Most claimed meal type": """
            SELECT f.Meal_Type, COUNT(c.Claim_ID) AS total_claims
            FROM food_listings f
            JOIN claims c ON f.Food_ID = c.Food_ID
            GROUP BY f.Meal_Type
            ORDER BY total_claims DESC
            LIMIT 1
        """,

        # 14. Total food donated by each provider
        "Total food donated by each provider": """
            SELECT p.Name, SUM(f.Quantity) AS total_donated
            FROM providers p
            JOIN food_listings f ON p.Provider_ID = f.Provider_ID
            GROUP BY p.Name
            ORDER BY total_donated DESC
        """,

        # 15. Claims per city
        "Claims per city": """
            SELECT r.City, COUNT(c.Claim_ID) AS total_claims
            FROM claims c
            JOIN receivers r ON c.Receiver_ID = r.Receiver_ID
            GROUP BY r.City
            ORDER BY total_claims DESC
        """
    }

    # Dropdown
    query_choice = st.selectbox("Choose a query to run", list(query_options.keys()))

    # Run selected query
    df_query = load_df(query_options[query_choice])

    if not df_query.empty:
        st.dataframe(df_query, use_container_width=True)

        # ✅ FIX: Only plot if there are at least 2 columns
        if df_query.shape[1] > 1:
            if ("count" in df_query.columns[1].lower() or
                "total" in df_query.columns[1].lower() or
                "sum" in df_query.columns[1].lower()):
                st.bar_chart(df_query.set_index(df_query.columns[0]))
    else:
        st.info("No results found for this query.")

# ---------- Settings ----------
elif page == "Settings / About":
    st.title("⚙️ Settings & About")
    st.write("Food Wastage Management System v2.0")
    st.write("Built with Streamlit, SQLite, Python, and Plotly for advanced visualization.")
