import os
import urllib.parse
import psycopg2 
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError
from flask import Flask, jsonify, request

app = Flask(__name__)

def conectar_banco():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    if not DATABASE_URL:
        raise ValueError("A variável DATABASE_URL não foi encontrada. Configure no Render!")
        
    conexao = psycopg2.connect(DATABASE_URL)
    return conexao

def criar_tabelas():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS caronas (
            id SERIAL PRIMARY KEY,
            origem TEXT,
            destino TEXT,
            horario TEXT,
            vagas TEXT,
            motorista TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS solicitacoes (
            id SERIAL PRIMARY KEY,
            carona_id INTEGER,
            passageiro TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefone TEXT NOT NULL,
            veiculo TEXT,
            placa TEXT,
            senha TEXT NOT NULL
        )
    """)

    conexao.commit()
    cursor.close()
    conexao.close()

criar_tabelas()

@app.route("/usuarios", methods=["POST"])
def cadastrar_usuario():
    dados = request.get_json()
    conexao = conectar_banco()
    cursor = conexao.cursor()
    try:
        cursor.execute("""
            INSERT INTO usuarios (nome, cpf, email, telefone, veiculo, placa, senha)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            dados["nome"], dados["cpf"], dados["email"], dados["telefone"],
            dados.get("veiculo", ""), dados.get("placa", ""), dados["senha"]
        ))
        conexao.commit()
        return jsonify({"mensagem": "Usuário guardado no cofre definitivo da nuvem!"}), 201
    except IntegrityError:
        conexao.rollback()
        return jsonify({"erro": "Esse CPF ou E-mail já está cadastrado!"}), 400
    finally:
        cursor.close()
        conexao.close()

@app.route("/verificar_cpf/<cpf_digitado>", methods=["GET"])
def checar_cpf(cpf_digitado):
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute("SELECT cpf FROM usuarios WHERE cpf = %s", (cpf_digitado,))
    usuario_encontrado = cursor.fetchone()
    cursor.close()
    conexao.close()
    
    if usuario_encontrado:
        return jsonify({"existe": True}), 200
    else:
        return jsonify({"existe": False}), 200

@app.route("/usuarios/<email_seguro>", methods=["DELETE"])
def excluir_conta(email_seguro):
    email_real = urllib.parse.unquote(email_seguro)
    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor) 
    
    cursor.execute("SELECT nome FROM usuarios WHERE email = %s", (email_real,))
    usuario = cursor.fetchone()
    
    if usuario:
        nome_usuario = usuario["nome"]
        cursor.execute("DELETE FROM caronas WHERE motorista = %s", (nome_usuario,))
        cursor.execute("DELETE FROM solicitacoes WHERE passageiro = %s", (nome_usuario,))
        cursor.execute("DELETE FROM usuarios WHERE email = %s", (email_real,))
        
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Conta e dados excluídos definitivamente!"}), 200
    else:
        cursor.close()
        conexao.close()
        return jsonify({"erro": "Usuário não encontrado."}), 404

@app.route("/login", methods=["POST"])
def login():
    dados = request.get_json()
    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT nome, cpf, email, telefone, veiculo, placa 
        FROM usuarios 
        WHERE email = %s AND senha = %s
    """, (dados["email"], dados["senha"]))

    usuario = cursor.fetchone()
    cursor.close()
    conexao.close()

    if usuario:
        return jsonify({
            "nome": usuario["nome"], "cpf": usuario["cpf"], "email": usuario["email"],
            "telefone": usuario["telefone"], "veiculo": usuario["veiculo"], "placa": usuario["placa"]
        }), 200
    else:
        return jsonify({"erro": "Acesso negado: E-mail ou senha inválidos."}), 401

@app.route("/caronas", methods=["GET"])
def listar_caronas():
    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM caronas")
    caronas_do_cofre = cursor.fetchall()
    cursor.close()
    conexao.close()

    lista_caronas = []
    for carona in caronas_do_cofre:
        lista_caronas.append({
            "id": carona["id"], "origem": carona["origem"], "destino": carona["destino"],
            "horario": carona["horario"], "vagas": carona["vagas"], "motorista": carona["motorista"]
        })
    return jsonify(lista_caronas)

@app.route("/caronas", methods=["POST"])
def criar_carona():
    nova_carona = request.get_json()
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("DELETE FROM caronas WHERE motorista = %s", (nova_carona["motorista"],))
    cursor.execute("""
        INSERT INTO caronas (origem, destino, horario, vagas, motorista)
        VALUES (%s, %s, %s, %s, %s)
    """, (nova_carona["origem"], nova_carona["destino"], nova_carona["horario"], nova_carona["vagas"], nova_carona["motorista"]))

    conexao.commit()
    cursor.close()
    conexao.close()
    return jsonify({"mensagem": "Carona salva sem duplicidades!"}), 201

@app.route("/caronas/<int:id_carona>", methods=["DELETE"])
def deletar_carona(id_carona):
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM caronas WHERE id = %s", (id_carona,))
    cursor.execute("DELETE FROM solicitacoes WHERE carona_id = %s", (id_carona,))
    conexao.commit()
    cursor.close()
    conexao.close()
    return jsonify({"mensagem": "Evento e solicitações excluídos!"}), 200

@app.route("/solicitacoes", methods=["GET"])
def listar_solicitacoes():
    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM solicitacoes")
    solicitacoes_do_cofre = cursor.fetchall()
    cursor.close()
    conexao.close()

    lista_solicitacoes = []
    for sol in solicitacoes_do_cofre:
        lista_solicitacoes.append({
            "id": sol["id"], "carona_id": sol["carona_id"], "passageiro": sol["passageiro"], "status": sol["status"]
        })
    return jsonify(lista_solicitacoes), 200

@app.route("/solicitacoes", methods=["POST"])
def pedir_carona():
    dados = request.get_json()
    carona_id = int(dados["carona_id"])

    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT vagas FROM caronas WHERE id = %s", (carona_id,))
    resultado = cursor.fetchone()

    # SEM SUBTRAÇÃO DAS VAGAS AQUI!
    if resultado:
        vagas_atuais = int(resultado["vagas"])
        if vagas_atuais > 0:
            cursor.execute("""
                INSERT INTO solicitacoes (carona_id, passageiro, status)
                VALUES (%s, %s, %s)
            """, (carona_id, dados["passageiro"], "Pendente"))

            conexao.commit()
            cursor.close()
            conexao.close()
            return jsonify({"mensagem": "Pedido registrado com sucesso!"}), 201

    cursor.close()
    conexao.close()
    return jsonify({"erro": "Não foi possível processar: Carona sem vagas ou inexistente."}), 400

@app.route("/solicitacoes/<int:id_solicitacao>", methods=["PUT"])
def responder_solicitacao(id_solicitacao):
    dados = request.get_json()
    novo_status = dados["status"]

    conexao = conectar_banco()
    cursor = conexao.cursor(cursor_factory=RealDictCursor)

    cursor.execute("UPDATE solicitacoes SET status = %s WHERE id = %s", (novo_status, id_solicitacao))

    conexao.commit()
    cursor.close()
    conexao.close()
    return jsonify({"mensagem": f"Status atualizado para {novo_status}!"}), 200

@app.route("/solicitacoes/<int:id_solicitacao>", methods=["DELETE"])
def cancelar_solicitacao(id_solicitacao):
    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    # Deleta a solicitação específica do banco
    cursor.execute("DELETE FROM solicitacoes WHERE id = %s", (id_solicitacao,))
    
    conexao.commit()
    cursor.close()
    conexao.close()
    
    return jsonify({"mensagem": "Pedido cancelado pelo passageiro e vaga devolvida!"}), 200

if __name__ == "__main__":
    print("🚀 Foguete FazFavor online, Matemática Corrigida DEFINITIVAMENTE!")
    porta = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=porta)