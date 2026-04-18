# Opcao B: para legenda, instale com: pip install openai-whisper

import os
import pathlib
import re
import shutil
import asyncio
import subprocess
import edge_tts
import json
import warnings
import sys
import time
import threading

try:
    import whisper
except ImportError:
    whisper = None

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe")

VOZES = {
    "1": {  # Mulher
        "nome": "mulher",
        "imagem": "locutora.png",
        "idiomas": {
            "1": ("italiano", "it-IT-IsabellaNeural"),
            "2": ("croata", "hr-HR-GabrijelaNeural"),
            "3": ("ingles", "en-US-EmmaMultilingualNeural"),
            "4": ("portugues-br", "pt-BR-FranciscaNeural"),
            "5": ("portugues-pt", "pt-PT-RaquelNeural"),
            "6": ("servio", "sr-RS-SophieNeural"),
            "7": ("espanhol", "es-ES-ElviraNeural"),
            "8": ("ingles-uk", "en-GB-SoniaNeural"),
            "9": ("frances", "fr-FR-VivienneMultilingualNeural"),
        }
    },
    "2": {  # Homem
        "nome": "homem",
        "imagem": "locutor.png",
        "idiomas": {
            "1": ("italiano", "it-IT-DiegoNeural"),
            "2": ("croata", "hr-HR-SreckoNeural"),
            "3": ("ingles", "en-US-ChristopherNeural"),
            "4": ("portugues-br", "pt-BR-AntonioNeural"),
            "5": ("portugues-pt", "pt-PT-DuarteNeural"),
            "6": ("servio", "sr-RS-NicholasNeural"),
            "7": ("espanhol", "es-ES-AlvaroNeural"),
            "8": ("ingles-uk", "en-GB-RyanNeural"),
            "9": ("frances", "fr-FR-RemyMultilingualNeural"),
        }
    }
}

# Classe para gerenciar o rodapé dinâmico com spinner e progresso
def barra_progresso(etapa_atual, total_etapas, titulo=""):
    progresso = int((etapa_atual / total_etapas) * 20)
    barra = "#" * progresso + "-" * (20 - progresso)
    print(f"[{barra}] {etapa_atual}/{total_etapas} - {titulo}")

class RodapeDinamico:
    def __init__(self):
        self.ativo = False
        self.thread = None
        self.mensagem = ""
        self.etapa_atual = 0
        self.total_etapas = 0
        self.spinner_chars = ['\\', '|', '/', '-']
        self.spinner_index = 0

    def iniciar(self, mensagem, etapa_atual, total_etapas):
        self.mensagem = mensagem
        self.etapa_atual = etapa_atual
        self.total_etapas = total_etapas
        self.ativo = True
        self.thread = threading.Thread(target=self._rodar)
        self.thread.start()

    def atualizar(self, mensagem=None, etapa_atual=None):
        if mensagem:
            self.mensagem = mensagem
        if etapa_atual:
            self.etapa_atual = etapa_atual

    def parar(self, mensagem_final=""):
        self.ativo = False
        if self.thread:
            self.thread.join()
        if mensagem_final:
            progresso = int((self.etapa_atual / self.total_etapas) * 20)
            barra = "#" * progresso + "-" * (20 - progresso)
            print(f"[{barra}] {self.etapa_atual}/{self.total_etapas} - {mensagem_final}")
        else:
            print()  # Limpar linha

    def _rodar(self):
        while self.ativo:
            progresso = int((self.etapa_atual / self.total_etapas) * 20)
            barra = "#" * progresso + "-" * (20 - progresso)
            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            sys.stdout.write(f"\r[{barra}] {self.etapa_atual}/{self.total_etapas} | {self.mensagem} {spinner}")
            sys.stdout.flush()
            self.spinner_index += 1
            time.sleep(0.15)

rodape = RodapeDinamico()

def limpar_pastas_temporarias(script_dir):
    for item in script_dir.iterdir():
        if item.is_file() and item.name.startswith('historia_') and item.name.endswith(('.mp3', '.mp4')):
            item.unlink()
        elif item.name == 'legenda_temp.ass':
            item.unlink()
        elif item.name == 'historia_bruto.mp3':
            item.unlink()

def split_text_into_blocks(text, max_chars):
    words = text.split()
    blocks = []
    current_block = ""
    for word in words:
        if len(current_block) + len(word) + 1 <= max_chars:
            current_block += word + " "
        else:
            blocks.append(current_block.strip())
            current_block = word + " "
    if current_block:
        blocks.append(current_block.strip())
    return blocks

def transformar_texto_para_leitura_fluida(texto, max_chars_por_bloco=450):
    blocos = split_text_into_blocks(texto, max_chars_por_bloco)
    return blocos

def normalizar_nome_para_arquivo(nome):
    return re.sub(r'[^a-zA-Z0-9_]', '_', nome).lower()

def escolher_voz_e_imagem():
    print("Quem narra?")
    print("1 - Mulher")
    print("2 - Homem")
    while True:
        escolha_sexo = input("Digite a opcao (1 ou 2): ").strip()
        if escolha_sexo in VOZES:
            break
        print("Opcao invalida. Tente novamente.")
    
    sexo_escolhido = VOZES[escolha_sexo]["nome"]
    imagem_nome = VOZES[escolha_sexo]["imagem"]
    
    print("Digite a opcao do idioma para narracao:")
    print("1 - Italiano")
    print("2 - Croata")
    print("3 - Ingles")
    print("4 - Portugues-br")
    print("5 - Portugues-pt")
    print("6 - Servio")
    print("7 - Espanhol")
    print("8 - Ingles-UK")
    print("9 - Frances")
    while True:
        escolha_idioma = input("Digite a opcao (1 a 9): ").strip()
        if escolha_idioma in VOZES[escolha_sexo]["idiomas"]:
            break
        print("Opcao invalida. Tente novamente.")
    
    idioma_escolhido, voice = VOZES[escolha_sexo]["idiomas"][escolha_idioma]
    return sexo_escolhido, idioma_escolhido, voice, imagem_nome

def perguntar_legenda():
    while True:
        resposta = input("Deseja adicionar legenda? (s/n): ").strip().lower()
        if resposta in ['s', 'n']:
            return resposta == 's'
        print("Resposta invalida. Digite 's' para sim ou 'n' para nao.")

def perguntar_efeitos():
    print("Escolha os efeitos de video:")
    print("1 - Barulho escuro")
    print("2 - Pendolo")
    print("3 - Zoom in e zoom out")
    print("4 - Barulho escuro + Pendolo")
    print("5 - Barulho escuro + Zoom in e zoom out")
    print("6 - Pendolo + Zoom in e zoom out")
    print("7 - Barulho escuro + Pendolo + Zoom in e zoom out")
    while True:
        escolha = input("Digite a opcao (1 a 7): ").strip()
        if escolha == '1':
            return "barulho_escuro"
        elif escolha == '2':
            return "pendolo"
        elif escolha == '3':
            return "zoom_in_out"
        elif escolha == '4':
            return "barulho_pendolo"
        elif escolha == '5':
            return "barulho_zoom"
        elif escolha == '6':
            return "pendolo_zoom"
        elif escolha == '7':
            return "todos"
        print("Opcao invalida. Tente novamente.")

def formatar_tempo_ass(segundos):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    seg = int(segundos % 60)
    centesimos = int((segundos % 1) * 100)
    return f"{horas:01d}:{minutos:02d}:{seg:02d}.{centesimos:02d}"

def gerar_ass_legenda_whisper(resultado_whisper, caminho_ass):
    with open(caminho_ass, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\n")
        f.write("Title: Legenda\n")
        f.write("ScriptType: v4.00+\n")
        f.write("WrapStyle: 0\n")
        f.write("ScaledBorderAndShadow: yes\n")
        f.write("\n[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n")
        f.write("\n[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for segmento in resultado_whisper['segments']:
            inicio = formatar_tempo_ass(segmento['start'])
            fim = formatar_tempo_ass(segmento['end'])
            texto = segmento['text'].strip()
            f.write(f"Dialogue: 0,{inicio},{fim},Default,,0,0,0,,{texto}\n")

def obter_duracao_audio(caminho_audio):
    if not os.path.exists(FFPROBE_PATH):
        return None
    try:
        resultado = subprocess.run([
            FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json', '-show_format', str(caminho_audio)
        ], capture_output=True, text=True, check=True)
        dados = json.loads(resultado.stdout)
        duracao = float(dados['format']['duration'])
        return duracao
    except:
        return None

def formatar_duracao(segundos):
    if segundos is None:
        return "N/A"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    seg = int(segundos % 60)
    return f"{horas:02d}:{minutos:02d}:{seg:02d}"

async def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    current_dir = pathlib.Path.cwd()
    historia_path = script_dir / "historia.txt"
    bruto_path = script_dir / "historia_bruto.mp3"
    
    print(f"Diretorio do script: {script_dir}")
    print(f"Diretorio atual: {current_dir}")
    
    limpar_pastas_temporarias(script_dir)
    
    escolha = escolher_voz_e_imagem()
    if not escolha:
        return
    sexo_escolhido, idioma_escolhido, voice, imagem_nome = escolha
    
    sexo_arquivo = normalizar_nome_para_arquivo(sexo_escolhido)
    idioma_arquivo = normalizar_nome_para_arquivo(idioma_escolhido)
    imagem_path = script_dir / imagem_nome
    final_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp3"
    video_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp4"
    
    if not historia_path.exists():
        print("Erro: historia.txt nao encontrado.")
        return
    
    if not imagem_path.exists():
        print(f"Erro: {imagem_nome} nao encontrado.")
        return
    
    if not os.path.exists(FFMPEG_PATH):
        print("Erro: ffmpeg.exe nao encontrado no caminho especificado.")
        return
    
    with open(historia_path, 'r', encoding='utf-8') as f:
        texto = f.read().strip()
    
    if not texto:
        print("Erro: historia.txt esta vazio.")
        return
    
    legenda = perguntar_legenda()
    if legenda and whisper is None:
        print("Erro: para a opcao B com legenda, instale openai-whisper.")
        return
    
    efeitos = perguntar_efeitos()
    
    blocos = transformar_texto_para_leitura_fluida(texto)
    
    total_etapas = 6 if legenda else 5
    etapa_atual = 1
    
    barra_progresso(etapa_atual, total_etapas, "Iniciando")
    
    # Etapa 1: Gerar áudio bruto
    rodape.iniciar("Gerando audio bruto...", etapa_atual, total_etapas)
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(str(bruto_path))
    rodape.parar("Audio bruto gerado.")
    etapa_atual += 1
    
    # Etapa 2: Remover silêncio
    rodape.iniciar("Removendo silencio...", etapa_atual, total_etapas)
    comando_silencio = [
        FFMPEG_PATH, '-y', '-i', str(bruto_path),
        '-af', 'silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-40dB',
        str(final_path)
    ]
    subprocess.run(comando_silencio, check=True)
    rodape.parar("Silencio removido.")
    etapa_atual += 1
    
    # Etapa 3: Obter durações
    rodape.iniciar("Obtendo duracoes...", etapa_atual, total_etapas)
    duracao_bruto = obter_duracao_audio(bruto_path)
    duracao_final = obter_duracao_audio(final_path)
    rodape.parar("Duracoes obtidas.")
    etapa_atual += 1
    
    print(f"Duracao do audio original: {formatar_duracao(duracao_bruto)}")
    print(f"Duracao do audio cortado : {formatar_duracao(duracao_final)}")
    
    # Etapa 4: Gerar legenda se necessário
    if legenda:
        rodape.iniciar("Gerando legenda com Whisper...", etapa_atual, total_etapas)
        warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")
        modelo_whisper = whisper.load_model("base")
        resultado_whisper = modelo_whisper.transcribe(str(final_path), word_timestamps=True, verbose=False)
        legenda_temp_path = script_dir / "legenda_temp.ass"
        gerar_ass_legenda_whisper(resultado_whisper, str(legenda_temp_path))
        rodape.parar("Legenda gerada.")
        etapa_atual += 1
    
    # Etapa 5: Gerar vídeo
    rodape.iniciar("Gerando video...", etapa_atual, total_etapas)
    vf_base = "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    
    if efeitos == "barulho_escuro":
        vf = f"{vf_base},eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette"
    elif efeitos == "pendolo":
        vf = f"{vf_base},rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    elif efeitos == "zoom_in_out":
        vf = f"{vf_base},zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    elif efeitos == "barulho_pendolo":
        vf = f"{vf_base},eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    elif efeitos == "barulho_zoom":
        vf = f"{vf_base},eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    elif efeitos == "pendolo_zoom":
        vf = f"{vf_base},rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    elif efeitos == "todos":
        vf = f"{vf_base},eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    else:
        vf = vf_base
    
    if legenda:
        vf += f",ass=legenda_temp.ass"
    
    comando_video = [
        FFMPEG_PATH, '-y',
        '-loop', '1',
        '-framerate', '2',
        '-i', str(imagem_path),
        '-i', str(final_path),
        '-vf', vf,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-tune', 'stillimage',
        '-pix_fmt', 'yuv420p',
        '-r', '2',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',
        str(video_path)
    ]
    subprocess.run(comando_video, cwd=script_dir, check=True)
    rodape.parar("Video gerado.")
    
    # Limpeza
    if bruto_path.exists():
        bruto_path.unlink()
    if legenda and (script_dir / "legenda_temp.ass").exists():
        (script_dir / "legenda_temp.ass").unlink()
    limpar_pastas_temporarias(script_dir)
    
    print("Processo concluido com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())