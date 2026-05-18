import os
from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

# 1. A CHAVE DO COFRE
def conectar_banco():
    conexao = sqlite3.connect('banco_fazfavor.db')
    conexao.row_factory = sqlite3.Row 
    return conexao

# 2. O CARPINTEIRO ATUALIZADO (Duas gavetas persistentes e integradas)
def criar_tabelas():
    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    # Gaveta 1: Caronas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS caronas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem TEXT,
            destino TEXT,
            horario TEXT,
            vagas TEXT,
            motorista TEXT
        )
    ''')
    
    # Gaveta 2: Solicitações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carona_id INTEGER,
            passageiro TEXT,
            status TEXT
        )
    ''')
    
    conexao.commit()
    conexao.close()

criar_tabelas()

# ==========================================
# ROTAS DE CARONAS
# ==========================================
@app.route('/caronas', methods=['GET'])
def listar_caronas():
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute('SELECT * FROM caronas')
    caronas_do_cofre = cursor.fetchall()
    conexao.close()
    
    lista_caronas = []
    for carona in caronas_do_cofre:
        lista_caronas.append({
            "id": carona["id"],
            "origem": carona["origem"],
            "destino": carona["destino"],
            "horario": carona["horario"],
            "vagas": carona["vagas"],
            "motorista": carona["motorista"]
        })
    return jsonify(lista_caronas)

@app.route('/caronas', methods=['POST'])
def criar_carona():
    nova_carona = request.get_json()
    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    # 🛡️ REGRA ANTI-DUPLICIDADE
    cursor.execute('DELETE FROM caronas WHERE motorista = ?', (nova_carona['motorista'],))
    
    cursor.execute('''
        INSERT INTO caronas (origem, destino, horario, vagas, motorista)
        VALUES (?, ?, ?, ?, ?)
    ''', (nova_carona['origem'], nova_carona['destino'], nova_carona['horario'], nova_carona['vagas'], nova_carona['motorista']))
    
    conexao.commit()
    conexao.close()
    return jsonify({"mensagem": "Carona salva sem duplicidades!"}), 201

@app.route('/caronas/<int:id_carona>', methods=['DELETE'])
def deletar_carona(id_carona):
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute('DELETE FROM caronas WHERE id = ?', (id_carona,))
    cursor.execute('DELETE FROM solicitacoes WHERE carona_id = ?', (id_carona,)) # Limpa os pedidos órfãos
    conexao.commit()
    conexao.close()
    return jsonify({"mensagem": "Evento e solicitações excluídos!"}), 200

# ==========================================
# ROTAS DE SOLICITAÇÕES (Logica de Vagas Centralizada)
# ==========================================

@app.route('/solicitacoes', methods=['GET'])
def listar_solicitacoes():
    conexao = conectar_banco()
    cursor = conexao.cursor()
    cursor.execute('SELECT * FROM solicitacoes')
    solicitacoes_do_cofre = cursor.fetchall()
    conexao.close()
    
    lista_solicitacoes = []
    for sol in solicitacoes_do_cofre:
        lista_solicitacoes.append({
            "id": sol["id"],
            "carona_id": sol["carona_id"],
            "passageiro": sol["passageiro"],
            "status": sol["status"]
        })
    return jsonify(lista_solicitacoes), 200

# 1. Passageiro pede a carona (Aqui a vaga diminui se houver espaço!)
@app.route('/solicitacoes', methods=['POST'])
def pedir_carona():
    dados = request.get_json()
    carona_id = int(dados['carona_id'])
    
    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    # 🕵️‍♂️ Investigação: Verifica quantas vagas reais ainda existem no banco
    cursor.execute('SELECT vagas FROM caronas WHERE id = ?', (carona_id,))
    resultado = cursor.fetchone()
    
    if resultado:
        vagas_atuais = int(resultado['vagas'])
        if vagas_atuais > 0:
            # ⬇️ Diminui 1 vaga na tabela de Caronas de forma definitiva
            novas_vagas = vagas_atuais - 1
            cursor.execute('UPDATE caronas SET vagas = ? WHERE id = ?', (str(novas_vagas), carona_id))
            
            # 📝 Registra o pedido como "Pendente" no caderno de solicitações
            cursor.execute('''
                INSERT INTO solicitacoes (carona_id, passageiro, status)
                VALUES (?, ?, ?)
            ''', (carona_id, dados['passageiro'], 'Pendente'))
            
            conexao.commit()
            conexao.close()
            return jsonify({"mensagem": "Pedido registrado e vaga reservada!"}), 201
            
    conexao.close()
    return jsonify({"erro": "Não foi possível processar: Carona sem vagas ou inexistente."}), 400

# 2. Motorista Aceita ou Recusa o pedido
@app.route('/solicitacoes/<int:id_solicitacao>', methods=['PUT'])
def responder_solicitacao(id_solicitacao):
    dados = request.get_json()
    novo_status = dados['status'] # "Aceito" ou "Recusado"
    
    conexao = conectar_banco()
    cursor = conexao.cursor()
    
    # Se o motorista clicar em Recusar, precisamos devolver a vaga que foi reservada!
    if novo_status == "Recusado":
        cursor.execute('SELECT carona_id FROM solicitacoes WHERE id = ?', (id_solicitacao,))
        solicitacao = cursor.fetchone()
        if solicitacao:
            carona_id = solicitacao['carona_id']
            cursor.execute('SELECT vagas FROM caronas WHERE id = ?', (carona_id,))
            carona = cursor.fetchone()
            if carona:
                # ⬆️ Devolve a vaga para o total da carona
                vagas_restauradas = int(carona['vagas']) + 1
                cursor.execute('UPDATE caronas SET vagas = ? WHERE id = ?', (str(vagas_restauradas), carona_id))
    
    # Atualiza o status do pedido
    cursor.execute('''
        UPDATE solicitacoes 
        SET status = ? 
        WHERE id = ?
    ''', (novo_status, id_solicitacao))
    
    conexao.commit()
    conexao.close()
    return jsonify({"mensagem": f"Status atualizado para {novo_status}!"}), 200

# Ligar os motores do servidor preparado para a nuvem!
if __name__ == '__main__':
    print("🚀 Foguete FazFavor online e preparado para a Nuvem!")
    porta = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=porta)