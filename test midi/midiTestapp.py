from flask import Flask, render_template
from jianpu_api import bp as jianpu_bp

app = Flask(__name__)
app.register_blueprint(jianpu_bp)

@app.get("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
