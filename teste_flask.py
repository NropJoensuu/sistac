from flask import Flask, jsonify

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

@app.route('/')
def index():
    return '<h1>Página inicial do SISTAC</h1>'

@app.route('/teste')
def teste():
    return '<h1>Olá! Minha primeira rota Python!</h1>'

@app.route('/sobre')
def sobre():
    return '<h1>Sistema de Gestão de TEDs e Convênios</h1>'

@app.route('/info')
def info():
    sistema = {
        'versao': '5.0.13',
        'nome': 'SISTAC',
        'modulos': ['Acordos', 'Convênios', 'Bolsas', 'Demandas']
    }
    return jsonify(sistema)

if __name__ == '__main__':
    app.run(port=5003, debug=True)