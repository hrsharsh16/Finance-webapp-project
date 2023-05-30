import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    Portfolios = db.execute("SELECT * FROM purchases WHERE user_id = (SELECT id FROM users WHERE id = ?)", session["user_id"])
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

     # Calculate the total cost of all stocks
    total_cost = sum(row["cost"] for row in Portfolios)

    # Add the current cash to the total
    total = total_cost + user_cash
    total = usd(total)
    u_cash = usd(user_cash)
    #current price of stocks
    for row in Portfolios:
        symbol = row["symbol"]
        price = lookup(symbol)["price"]
        price = usd(price)
        row["current_price"] = price
        #convert price into usd notation
        USD = row["price"]
        Usd = usd(USD)
        row["price"] = Usd
        #convert cost to usd
        change = row["cost"]
        changed = usd(change)
        row["cost"] = changed
        #convert current price to usd

    return render_template("index.html", portfolios=Portfolios, cash = u_cash, total =  total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method =="POST":

        BOUGHT = lookup( request.form.get("symbol"))
        if BOUGHT is None:
            # Handle case where lookup returns None
            return apology("no such symbol", 400)

        PRICE = BOUGHT["price"]
        SYMBOL = BOUGHT["symbol"]
        Shares = int(request.form.get("shares"))

        try:
            shares = int(Shares)
        except ValueError:
            return apology("Invalid number of shares")

        if shares <= 0:
             return apology("Invalid number of shares")

        user_id = session["user_id"]

         # Retrieve user's cash balance from database
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        # Calculate cost of purchase
        cost = Shares*PRICE

        # Check if user can afford purchase
        if cost > user_cash:
            return apology("not enough cash to purchase")

        # Update user's cash balance
        db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", cost, session["user_id"])
        # Insert new row into purchases table
        db.execute("INSERT INTO purchases (user_id, symbol, price, quantity, cost) VALUES (?, ?, ?, ?, ?)", user_id, SYMBOL, PRICE, Shares, cost)
        db.execute("INSERT INTO buy (user_id, symbol, price, quantity) VALUES (?, ?, ?, ?)", user_id, SYMBOL, PRICE, Shares)


        return redirect(url_for("index"))

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # get all transactions from sell and buy tables for the current user
    transactions = db.execute("SELECT *, 'sell' as type FROM sell WHERE user_id = ? UNION SELECT *, 'buy' as type FROM buy WHERE user_id = ?", session["user_id"], session["user_id"])

    # render the history.html template with the transactions as a parameter
    return render_template("history.html", transactions=transactions)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        QUOTES = lookup( request.form.get("symbol"))
        if QUOTES is None:
            # Handle case where lookup returns None
            return apology("no such symbol", 400)
        NAME = QUOTES["name"]
        PRICE = QUOTES["price"]
        SYMBOL = QUOTES["symbol"]

        Price = usd(PRICE)
        return render_template("quoted.html", name=NAME, Symbol=SYMBOL, price=Price)
    else:
        # return for GET
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # check for errors & insert user in users table login

         # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)


        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was REsubmitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        # Ensure password and confirmation are the same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation must match", 400)

        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))
        #   adding into userbase
        db.execute ("INSERT INTO users (username, hash, cash) VALUES (?, ?, ?)", username, hash, 10000.00)
        return render_template("login.html")




    else:
        # Display for GET
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method =="POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if int(shares) <= 0:
            return apology("Invalid number of shares")


        #check if user has the stock and shares
        current = db.execute("SELECT * FROM purchases WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)

        owned_shares = 0
        for stock in current:
            if stock["symbol"] == symbol:
                owned_shares += stock["quantity"]
            if owned_shares < int(shares):
                return apology("You do not own enough shares.")
        # update stocks in database
        db.execute("UPDATE purchases SET quantity = quantity - ? WHERE user_id = ? AND symbol = ?", shares, session["user_id"], symbol)

        # Get current market price of the stock
        price = lookup(symbol)["price"]
        # Calculate the cost of the transaction
        cost = price * int(shares)
        # update the cash in the users table
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", user_cash + cost, session["user_id"])
        db.execute("INSERT INTO sell (user_id, symbol, quantity, price) VALUES (?, ?, ?, ?)", session["user_id"], symbol, shares, price)


        return redirect(url_for("index"))
    else:
        stocks = db.execute("SELECT * FROM purchases WHERE user_id = (SELECT id FROM users WHERE id = ?)", session["user_id"])
        return render_template("sell.html", stocks = stocks)

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method =="POST":
        amount = request.form.get("amount")
        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        new_cash = int(amount) + int(user_cash)
        #add cash in db
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        return redirect(url_for("index"))


    else:
        return render_template("add.html")
