"""Ponto de entrada para desenvolvimento: python run.py"""
from catalogo import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
