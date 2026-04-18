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

def limpar_pastas_temporarias(script_dir):
    pastas_temp = ["temp", "tmp"]
    for pasta in pastas_temp:
        caminho_pasta = script_dir / pasta
        if caminho_pasta.exists():
            shutil.rmtree(caminho_pasta)
            print(f"Pasta temporaria '{pasta}' removida.")

def split_text_into_blocks(text, max_chars):
    words = text.split()
    blocks = []
    current_block = ""
    for word in words:
        if len(current_block) + len(word) + 1 <= max_chars:
            current_block += " " + word if current_block else word
        else:
            blocks.append(current_block)
            current_block = word
    if current_block:
        blocks.append(current_block)
    return blocks

def transformar_texto_para_leitura_fluida(texto, max_chars_por_bloco=450):
    blocos = split_text_into_blocks(texto, max_chars_por_bloco)
    texto_transformado = "\n\n".join(blocos)
    return texto_transformado

def normalizar_nome_para_arquivo(nome):
    nome_normalizado = re.sub(r'[^a-zA-Z0-9_-]', '_', nome)
    return nome_normalizado.lower()

def escolher_voz_e_imagem():
    print("Quem narra?")
    print("1 - Mulher")
    print("2 - Homem")
    sexo = input("Digite a opcao do sexo: ").strip()
    if sexo not in VOZES:
        print("Opcao invalida.")
        return None
    
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
    idioma = input("Digite a opcao do idioma: ").strip()
    if idioma not in VOZES[sexo]["idiomas"]:
        print("Opcao invalida.")
        return None
    
    idioma_nome, voice = VOZES[sexo]["idiomas"][idioma]
    imagem_nome = VOZES[sexo]["imagem"]
    return VOZES[sexo]["nome"], idioma_nome, voice, imagem_nome

def perguntar_efeitos():
    print("Deseja adicionar efeitos ao video?")
    print("1 - Sim")
    print("2 - Nao")
    opcao = input("Digite a opcao: ").strip()
    if opcao == "2":
        return None
    elif opcao == "1":
        print("Qual efeito deseja adicionar?")
        print("1 - Barulho escuro")
        print("2 - Pendolo")
        print("3 - Ambos")
        print("4 - Zoom in e zoom out")
        print("5 - Pendolo + Zoom in e zoom out")
        efeito = input("Digite a opcao do efeito: ").strip()
        if efeito == "1":
            return "barulho_escuro"
        elif efeito == "2":
            return "pendolo"
        elif efeito == "3":
            return "ambos"
        elif efeito == "4":
            return "zoom_in_out"
        elif efeito == "5":
            return "pendolo_zoom"
        else:
            print("Opcao invalida.")
            return None
    else:
        print("Opcao invalida.")
        return None

def perguntar_legenda():
    print("Deseja adicionar legenda ao video?")
    print("1 - Sim")
    print("2 - Nao")
    opcao = input("Digite a opcao: ").strip()
    if opcao == "1":
        return True
    elif opcao == "2":
        return False
    else:
        print("Opcao invalida.")
        return None

def formatar_tempo_ass(segundos):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segundos_restantes = segundos % 60
    centesimos = int((segundos_restantes % 1) * 100)
    return f"{horas}:{minutos:02d}:{int(segundos_restantes):02d}.{centesimos:02d}"

def gerar_ass_legenda_whisper(resultado_whisper, caminho_ass):
    with open(caminho_ass, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("Collisions: Normal\n")
        f.write("PlayResX: 854\n")
        f.write("PlayResY: 480\n")
        f.write("\n[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,24,&H00FFFF00,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n")
        f.write("\n[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for segment in resultado_whisper["segments"]:
            for word in segment.get("words", []):
                start = formatar_tempo_ass(word["start"])
                end = formatar_tempo_ass(word["end"])
                text = word["word"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

def obter_duracao_audio(caminho_audio):
    if not os.path.exists(FFPROBE_PATH):
        return None
    try:
        result = subprocess.run([
            FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json', '-show_format', str(caminho_audio)
        ], capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except:
        return None

def formatar_duracao(segundos):
    if segundos is None:
        return "N/A"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segundos_restantes = int(segundos % 60)
    return f"{horas:02d}:{minutos:02d}:{segundos_restantes:02d}"

def barra_progresso(etapa_atual, total_etapas, titulo=""):
    progresso = int((etapa_atual / total_etapas) * 20)
    barra = "#" * progresso + "-" * (20 - progresso)
    print(f"[{barra}] {etapa_atual}/{total_etapas} - {titulo}")

async def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    current_dir = pathlib.Path.cwd()
    print(f"Diretorio do script: {script_dir}")
    print(f"Diretorio atual: {current_dir}")
    
    limpar_pastas_temporarias(script_dir)
    
    escolha = escolher_voz_e_imagem()
    if not escolha:
        return
    sexo_escolhido, idioma_escolhido, voice, imagem_nome = escolha
    
    efeitos = perguntar_efeitos()
    legenda = perguntar_legenda()
    
    sexo_arquivo = normalizar_nome_para_arquivo(sexo_escolhido)
    idioma_arquivo = normalizar_nome_para_arquivo(idioma_escolhido)
    
    historia_path = script_dir / "historia.txt"
    bruto_path = script_dir / "historia_bruto.mp3"
    imagem_path = script_dir / imagem_nome
    final_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp3"
    video_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp4"
    
    if not historia_path.exists():
        print("Erro: arquivo historia.txt nao encontrado.")
        return
    
    if not imagem_path.exists():
        print(f"Erro: imagem {imagem_nome} nao encontrada.")
        return
    
    if not os.path.exists(FFMPEG_PATH):
        print("Erro: ffmpeg.exe nao encontrado no caminho especificado.")
        return
    
    with open(historia_path, 'r', encoding='utf-8') as f:
        texto = f.read().strip()
    
    if not texto:
        print("Erro: historia.txt esta vazio.")
        return
    
    if legenda and whisper is None:
        print("Erro: para a opcao B com legenda, instale openai-whisper.")
        return
    
    total_etapas = 6
    
    barra_progresso(1, total_etapas, "transformando texto para leitura fluida")
    texto_transformado = transformar_texto_para_leitura_fluida(texto)
    
    barra_progresso(2, total_etapas, "gerando audio bruto com edge-tts")
    communicate = edge_tts.Communicate(texto_transformado, voice)
    await communicate.save(str(bruto_path))
    
    barra_progresso(3, total_etapas, "removendo silencios com FFmpeg")
    subprocess.run([
        FFMPEG_PATH, '-y', '-i', str(bruto_path), '-af', 'silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-40dB', str(final_path)
    ])
    
    barra_progresso(4, total_etapas, "obtendo duracao dos audios")
    duracao_bruto = obter_duracao_audio(bruto_path)
    duracao_final = obter_duracao_audio(final_path)
    print(f"Duracao do audio original: {formatar_duracao(duracao_bruto)}")
    print(f"Duracao do audio cortado : {formatar_duracao(duracao_final)}")
    
    if legenda:
        barra_progresso(5, total_etapas, "gerando legenda com Whisper")
        warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")
        modelo_whisper = whisper.load_model("base")
        resultado_whisper = modelo_whisper.transcribe(str(final_path), word_timestamps=True, verbose=False)
        legenda_temp_path = script_dir / "legenda_temp.ass"
        gerar_ass_legenda_whisper(resultado_whisper, str(legenda_temp_path))
    else:
        barra_progresso(5, total_etapas, "pulando legenda")
    
    barra_progresso(6, total_etapas, "gerando video com a imagem selecionada")
    vf = "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    if efeitos == "barulho_escuro":
        vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette"
    elif efeitos == "pendolo":
        vf += ",rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    elif efeitos == "ambos":
        vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    elif efeitos == "zoom_in_out":
        vf += ",zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    elif efeitos == "pendolo_zoom":
        vf += ",rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    if legenda:
        vf += f",ass=legenda_temp.ass"
    
    subprocess.run([
        FFMPEG_PATH, '-y', '-loop', '1', '-framerate', '2', '-i', str(imagem_path), '-i', str(final_path),
        '-vf', vf, '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-pix_fmt', 'yuv420p',
        '-r', '2', '-c:a', 'aac', '-b:a', '128k', '-shortest', str(video_path)
    ], cwd=script_dir)
    
    if bruto_path.exists():
        os.remove(bruto_path)
    if legenda and (script_dir / "legenda_temp.ass").exists():
        os.remove(script_dir / "legenda_temp.ass")
    
    limpar_pastas_temporarias(script_dir)
    
    print("Video gerado com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
