from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests
import os
import csv
import io
from datetime import datetime
from database import (
    get_memory_by_text,
    add_memory,
    get_all_memories,
    delete_memory,
    clear_all_memories,
    get_all_terminology,
    add_terminology,
    delete_terminology,
    clear_all_terminology,
    find_matching_terms,
    add_vocabulary,
    get_all_vocabulary,
    get_unmastered_vocabulary,
    update_vocabulary_mastered,
    delete_vocabulary,
    clear_all_vocabulary,
    update_vocabulary,
    add_vocabulary_meaning,
)

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator, DeeplTranslator
    DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    DEEP_TRANSLATOR_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

app = FastAPI(title="中法互译工具 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranslateRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    api_key: str = ""
    api_service: str = "free"
    model: str = "free"

class ImportTermsRequest(BaseModel):
    terms: list[dict]

class TranscribeRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    api_key: str = ""
    api_service: str = "free"

class ApiConfigRequest(BaseModel):
    api_key: str
    api_service: str
    model: str
    base_url: str = ""

class VocabularyUpdateRequest(BaseModel):
    mastered: int

def segment_text(text, source_lang):
    paragraphs = []
    
    if source_lang == 'zh':
        text = text.replace('\r\n', '\n')
        raw_paragraphs = text.split('\n\n')
        
        for para in raw_paragraphs:
            para = para.strip()
            if para:
                sentences = []
                current_sentence = ''
                
                for char in para:
                    current_sentence += char
                    if char in '。！？；\n':
                        sentences.append(current_sentence.strip())
                        current_sentence = ''
                
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                
                paragraphs.append({
                    'text': para,
                    'sentences': sentences
                })
    else:
        text = text.replace('\r\n', '\n')
        raw_paragraphs = text.split('\n\n')
        
        for para in raw_paragraphs:
            para = para.strip()
            if para:
                sentences = []
                current_sentence = ''
                
                for char in para:
                    current_sentence += char
                    if char in '.!?;\n':
                        sentences.append(current_sentence.strip())
                        current_sentence = ''
                
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                
                paragraphs.append({
                    'text': para,
                    'sentences': sentences
                })
    
    return paragraphs

def extract_vocabulary(source_text, target_text, source_lang, target_lang):
    if source_lang == 'zh':
        chinese_text = source_text
        french_text = target_text
    else:
        chinese_text = target_text
        french_text = source_text
    
    chinese_words = [word.strip() for word in chinese_text.replace('，', ' ').replace('。', ' ').replace('！', ' ').replace('？', ' ').split() if len(word.strip()) >= 2]
    french_words = []
    for word in french_text.replace(',', ' ').replace('.', ' ').replace('!', ' ').replace('?', ' ').split():
        clean_word = word.strip().lower()
        if len(clean_word) >= 3:
            french_words.append(clean_word)
    
    for i in range(min(len(chinese_words), len(french_words))):
        add_vocabulary(french_words[i], 'fr', chinese_words[i], 'zh', source_text[:100])

def call_paid_api(text, source_lang, target_lang, api_key, api_service, model, base_url, terminology_hint=""):
    if source_lang == 'zh':
        source_name = "中文"
        target_name = "法语"
    else:
        source_name = "法语"
        target_name = "中文"
    
    system_prompt = f"你是一个专业的{source_name}到{target_name}翻译助手。请准确翻译以下文本。"
    if terminology_hint:
        system_prompt += f"\n请参考以下术语进行翻译：{terminology_hint}"
    
    user_prompt = f"请将以下{source_name}文本翻译成{target_name}：\n\n{text}"
    
    if api_service == "deepseek":
        url = base_url or "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
    elif api_service == "openai":
        url = base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
    else:
        raise HTTPException(status_code=400, detail="不支持的API服务")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译API调用失败: {str(e)}")

def translate_with_google_direct(text, source_lang, target_lang):
    lang_map = {
        'zh': 'zh-CN',
        'fr': 'fr'
    }
    
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        'client': 'gtx',
        'sl': lang_map.get(source_lang, source_lang),
        'tl': lang_map.get(target_lang, target_lang),
        'dt': 't',
        'q': text
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                translated_text = ""
                for item in result[0]:
                    if item and isinstance(item[0], str):
                        translated_text += item[0]
                if translated_text.strip() and translated_text != text:
                    return translated_text.strip()
                else:
                    raise Exception("翻译结果与原文相同")
        raise Exception(f"Google翻译返回错误: {response.status_code}")
    except Exception as e:
        raise Exception(f"Google翻译失败: {str(e)}")

def translate_with_google(text, source_lang, target_lang):
    try:
        return translate_with_google_direct(text, source_lang, target_lang)
    except Exception as e_direct:
        if DEEP_TRANSLATOR_AVAILABLE:
            try:
                lang_map = {
                    'zh': 'zh-CN',
                    'fr': 'fr'
                }
                translator = GoogleTranslator(
                    source=lang_map.get(source_lang, source_lang),
                    target=lang_map.get(target_lang, target_lang)
                )
                return translator.translate(text)
            except Exception as e_lib:
                raise Exception(f"Google翻译失败: {str(e_direct)}, {str(e_lib)}")
        else:
            raise Exception(f"Google翻译失败: {str(e_direct)}")

def translate_with_mymemory(text, source_lang, target_lang):
    if not DEEP_TRANSLATOR_AVAILABLE:
        raise Exception("deep-translator not installed")
    
    lang_map = {
        'zh': 'zh-CN',
        'fr': 'fr'
    }
    
    try:
        translator = MyMemoryTranslator(
            source=lang_map.get(source_lang, source_lang),
            target=lang_map.get(target_lang, target_lang)
        )
        return translator.translate(text)
    except Exception as e:
        raise Exception(f"MyMemory翻译失败: {str(e)}")

def translate_with_libre(text, source_lang, target_lang):
    lang_map = {
        'zh': 'zh',
        'fr': 'fr'
    }
    
    url = "https://libretranslate.de/translate"
    payload = {
        "q": text,
        "source": lang_map.get(source_lang, source_lang),
        "target": lang_map.get(target_lang, target_lang),
        "format": "text"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if "translatedText" in result:
            return result["translatedText"]
        raise Exception("API返回格式错误")
    except Exception as e:
        raise Exception(f"LibreTranslate失败: {str(e)}")

def translate_with_bing(text, source_lang, target_lang):
    lang_map = {
        'zh': 'zh-Hans',
        'fr': 'fr'
    }
    
    url = "https://api.cognitive.microsofttranslator.com/translate"
    params = {
        'api-version': '3.0',
        'from': lang_map.get(source_lang, source_lang),
        'to': lang_map.get(target_lang, target_lang)
    }
    
    try:
        response = requests.post(
            url,
            params=params,
            headers={'Content-Type': 'application/json'},
            json=[{'Text': text}],
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            if result and len(result) > 0 and 'translations' in result[0]:
                return result[0]['translations'][0]['text']
        raise Exception(f"Bing API返回错误: {response.status_code}")
    except Exception as e:
        raise Exception(f"Bing翻译失败: {str(e)}")

def translate_with_deepl(text, source_lang, target_lang, api_key=""):
    if not DEEP_TRANSLATOR_AVAILABLE:
        return translate_with_google_direct(text, source_lang, target_lang)
    
    lang_map = {
        'zh': 'zh-CN',
        'fr': 'fr'
    }
    
    try:
        if api_key:
            translator = DeeplTranslator(
                api_key=api_key,
                source=lang_map.get(source_lang, "auto"),
                target=lang_map.get(target_lang, target_lang),
                use_free_api=True
            )
            result = translator.translate(text)
            if result and result.strip() and result != text:
                return result.strip()
            raise Exception("DeepL返回空或原文")
        else:
            return translate_with_google_direct(text, source_lang, target_lang)
    except Exception as e:
        try:
            return translate_with_google_direct(text, source_lang, target_lang)
        except Exception as fallback_error:
            raise Exception(f"DeepL翻译失败: {str(e)}, 降级也失败: {str(fallback_error)}")

def extract_text_from_docx(content):
    if not DOCX_AVAILABLE:
        raise Exception("python-docx not installed")
    
    doc = Document(io.BytesIO(content))
    paragraphs = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    
    return "\n\n".join(paragraphs)

def extract_text_from_pptx(content):
    if not PPTX_AVAILABLE:
        raise Exception("python-pptx not installed")
    
    prs = Presentation(io.BytesIO(content))
    paragraphs = []
    
    for slide_num, slide in enumerate(prs.slides, 1):
        slide_texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_texts.append(shape.text.strip())
        if slide_texts:
            paragraphs.append(f"[幻灯片 {slide_num}]\n" + "\n".join(slide_texts))
    
    return "\n\n".join(paragraphs)

def call_translation_api(text, source_lang, target_lang, api_key, api_service, model, terminology_hint=""):
    text = text.strip()
    if not text:
        return ""
    
    all_engines = [
        ("Google直接API", lambda t: translate_with_google_direct(t, source_lang, target_lang)),
        ("LibreTranslate", lambda t: translate_with_libre(t, source_lang, target_lang)),
        ("MyMemory", lambda t: translate_with_mymemory(t, source_lang, target_lang)),
        ("Bing", lambda t: translate_with_bing(t, source_lang, target_lang)),
    ]
    
    if api_service == "google":
        translation_engines = all_engines[:2]
    elif api_service == "deepl":
        translation_engines = [
            ("DeepL", lambda t: translate_with_deepl(t, source_lang, target_lang, api_key)),
        ] + all_engines
    elif api_service == "mymemory":
        translation_engines = [all_engines[2]] + all_engines[:2]
    elif api_service == "libre":
        translation_engines = [all_engines[1]] + all_engines[:2]
    else:
        translation_engines = all_engines
    
    last_error = None
    for name, translate_func in translation_engines:
        try:
            result = translate_func(text)
            if result and result.strip() and result != text:
                return result
            last_error = f"{name}返回原文"
        except Exception as e:
            last_error = str(e)
            continue
    
    fallback_result = translate_with_rules(text, source_lang, target_lang, terminology_hint)
    if fallback_result and fallback_result != text:
        return fallback_result
    
    raise HTTPException(status_code=500, detail=f"所有翻译引擎失败: {last_error}")

def apply_terminology_override(source_text, translated_text, terminology_hint, source_lang):
    if not terminology_hint:
        return translated_text
    
    terms = terminology_hint.split(', ')
    for term in terms:
        if '=' in term:
            parts = term.split('=', 1)
            if source_lang == 'zh':
                original_term = parts[0].strip()
                target_term = parts[1].strip()
                if original_term in source_text and target_term not in translated_text:
                    translated_text = translated_text.replace(original_term, target_term)
            else:
                original_term = parts[0].strip()
                target_term = parts[1].strip()
                if original_term in source_text and target_term not in translated_text:
                    translated_text = translated_text.replace(original_term, target_term)
    return translated_text

def translate_with_rules(text, source_lang, target_lang, terminology_hint):
    common_phrases = {
        'zh': {
            '你好': 'Bonjour',
            '谢谢': 'Merci',
            '再见': 'Au revoir',
            '请': 'S\'il vous plaît',
            '对不起': 'Désolé',
            '是': 'Oui',
            '不': 'Non',
            '好的': 'D\'accord',
            '不知道': 'Je ne sais pas',
            '我': 'Je',
            '你': 'Tu/Vous',
            '他': 'Il',
            '她': 'Elle',
            '我们': 'Nous',
            '他们': 'Ils/Elles',
            '今天': 'Aujourd\'hui',
            '明天': 'Demain',
            '昨天': 'Hier',
            '时间': 'Temps',
            '工作': 'Travail',
            '学习': 'Étude',
            '学校': 'École',
            '家': 'Maison',
            '朋友': 'Ami',
            '家人': 'Famille',
            '爱': 'Amour',
            '幸福': 'Bonheur',
            '计算机': 'Ordinateur',
            '翻译': 'Traduction',
            '中文': 'Chinois',
            '法语': 'Français',
            '中国': 'Chine',
            '法国': 'France',
            '北京': 'Pékin',
            '巴黎': 'Paris',
            '你叫什么名字': 'Comment tu t\'appelles ?',
            '你好吗': 'Comment ça va ?',
            '很高兴见到你': 'Ravi de vous rencontrer',
            '请问': 'Excusez-moi',
            '多少钱': 'Combien ça coûte ?',
            '在哪里': 'Où est-ce ?',
            '我来自中国': 'Je viens de Chine',
            '我喜欢': 'J\'aime',
            '我想要': 'Je veux',
            '可以帮助我吗': 'Pouvez-vous m\'aider ?',
            '没关系': 'Ça va',
            '非常好': 'Très bien',
            '不客气': 'De rien',
            '早上好': 'Bonjour',
            '晚上好': 'Bonsoir',
            '再见': 'Au revoir',
            '欢迎': 'Bienvenue',
            '谢谢': 'Merci',
            '不用谢': 'De rien',
            '对不起': 'Désolé',
            '没关系': 'Ce n\'est pas grave',
            '请坐': 'Asseyez-vous',
            '请进': 'Entrez',
            '请问': 'Excusez-moi',
            '你会说中文吗': 'Parlez-vous chinois ?',
            '我不会说法语': 'Je ne parle pas français',
            '你能帮助我吗': 'Pouvez-vous m\'aider ?',
            '我想去': 'Je veux aller à',
            '多少钱': 'Combien ça coûte ?',
            '太贵了': 'C\'est trop cher',
            '便宜一点': 'Pas cher',
            '谢谢': 'Merci',
            '再见': 'Au revoir',
            '祝你好运': 'Bonne chance',
            '新年快乐': 'Bonne année',
            '生日快乐': 'Joyeux anniversaire',
            '再见': 'Au revoir',
            '好的': 'D\'accord',
            '是的': 'Oui',
            '不是': 'Non',
            '也许': 'Peut-être',
            '当然': 'Bien sûr',
            '可能': 'Probablement',
            '不可能': 'Impossible',
            '好': 'Bon',
            '坏': 'Mauvais',
            '大': 'Grand',
            '小': 'Petit',
            '长': 'Long',
            '短': 'Court',
            '高': 'Haut',
            '矮': 'Bas',
            '快': 'Vite',
            '慢': 'Lent',
            '多': 'Beaucoup',
            '少': 'Peu',
            '多': 'Plus',
            '少': 'Moins',
            '第一': 'Premier',
            '最后': 'Dernier',
            '现在': 'Maintenant',
            '以后': 'Plus tard',
            '以前': 'Avant',
            '今天': 'Aujourd\'hui',
            '明天': 'Demain',
            '昨天': 'Hier',
            '这个': 'Ceci/Cela',
            '那个': 'Celà',
            '这里': 'Ici',
            '那里': 'Là',
            '什么': 'Quoi',
            '谁': 'Qui',
            '哪里': 'Où',
            '什么时候': 'Quand',
            '为什么': 'Pourquoi',
            '怎么样': 'Comment',
            '多少': 'Combien',
            '哪个': 'Lequel/Laquelle',
            '和': 'Et',
            '或者': 'Ou',
            '但是': 'Mais',
            '所以': 'Donc',
            '因为': 'Parce que',
            '如果': 'Si',
            '虽然': 'Bien que',
            '而且': 'Et aussi',
            '却': 'Mais',
            '又': 'Encore',
            '才': 'Ce n\'est qu\'après',
            '就': 'Alors',
            '也': 'Aussi',
            '都': 'Tous',
            '只': 'Seulement',
            '很': 'Très',
            '太': 'Trop',
            '更': 'Plus',
            '最': 'Le plus',
            '不': 'Non',
            '没': 'Pas',
            '别': 'Ne...pas',
            '不要': 'Ne pas',
            '可以': 'Pouvoir',
            '会': 'Savoir',
            '想': 'Vouloir',
            '要': 'Devoir',
            '应该': 'Devrait',
            '必须': 'Doit',
            '需要': 'Avoir besoin de',
            '能': 'Pouvoir',
            '可能': 'Peut-être',
            '会': 'Va',
            '正在': 'En train de',
            '已经': 'Déjà',
            '还': 'Encore',
            '再': 'Encore',
            '又': 'Encore',
            '刚': 'Viens de',
            '马上': 'Tout de suite',
            '立刻': 'Immédiatement',
            '忽然': 'Soudain',
            '突然': 'Brusquement',
            '慢慢': 'Lentement',
            '快速': 'Rapidement',
            '仔细': 'Soigneusement',
            '认真': 'Sérieusement',
            '努力': 'Durement',
            '轻松': 'Facilement',
            '简单': 'Facile',
            '复杂': 'Compliqué',
            '困难': 'Difficile',
            '容易': 'Facile',
            '重要': 'Important',
            '必要': 'Nécessaire',
            '可能': 'Possible',
            '不可能': 'Impossible',
            '成功': 'Succès',
            '失败': 'Échec',
            '开始': 'Commencer',
            '结束': 'Finir',
            '继续': 'Continuer',
            '停止': 'Arrêter',
            '等待': 'Attendre',
            '希望': 'Espérer',
            '相信': 'Croire',
            '知道': 'Savoir',
            '了解': 'Comprendre',
            '学习': 'Apprendre',
            '工作': 'Travailler',
            '休息': 'Se reposer',
            '睡觉': 'Dormir',
            '吃饭': 'Manger',
            '喝水': 'Boire',
            '说话': 'Parler',
            '听': 'Écouter',
            '看': 'Regarder',
            '读': 'Lire',
            '写': 'Écrire',
            '做': 'Faire',
            '去': 'Aller',
            '来': 'Venir',
            '走': 'Marcher',
            '跑': 'Courir',
            '跳': 'Sauter',
            '飞': 'Voler',
            '游泳': 'Nager',
            '开车': 'Conduire',
            '坐': 'Assis',
            '站': 'Debout',
            '躺': 'Allongé',
            '走': 'Partir',
            '来': 'Venir',
            '回到': 'Retourner',
            '到达': 'Arriver',
            '离开': 'Quitter',
            '经过': 'Passer par',
            '穿过': 'Traverser',
            '进入': 'Entrer',
            '出去': 'Sortir',
            '上': 'Monter',
            '下': 'Descendre',
            '打开': 'Ouvrir',
            '关闭': 'Fermer',
            '拿': 'Prendre',
            '放': 'Poser',
            '给': 'Donner',
            '借': 'Emprunter',
            '还': 'Rendre',
            '买': 'Acheter',
            '卖': 'Vendre',
            '交换': 'Échanger',
            '接受': 'Accepter',
            '拒绝': 'Refuser',
            '同意': 'Accepter',
            '不同意': 'Refuser',
            '喜欢': 'Aimer',
            '讨厌': 'Détester',
            '爱': 'Aimer',
            '恨': 'Détester',
            '害怕': 'Avoir peur',
            '担心': 'S\'inquiéter',
            '高兴': 'Heureux',
            '难过': 'Triste',
            '生气': 'Fâché',
            '悲伤': 'Triste',
            '惊讶': 'Étonné',
            '兴奋': 'Excité',
            '累': 'Fatigué',
            '饿': 'Affamé',
            '渴': 'Assoiffé',
            '冷': 'Froid',
            '热': 'Chaud',
            '生病': 'Malade',
            '健康': 'Sain',
            '年轻': 'Jeune',
            '老': 'Vieux',
            '新': 'Nouveau',
            '旧': 'Ancien',
            '好': 'Bon',
            '坏': 'Mauvais',
            '美': 'Beau',
            '丑': 'Laid',
            '干净': 'Propre',
            '脏': 'Sale',
            '大': 'Grand',
            '小': 'Petit',
            '长': 'Long',
            '短': 'Court',
            '高': 'Haut',
            '矮': 'Bas',
            '宽': 'Large',
            '窄': 'Étroit',
            '厚': 'Épais',
            '薄': 'Fin',
            '重': 'Lourd',
            '轻': 'Léger',
            '快': 'Vite',
            '慢': 'Lent',
            '早': 'Tôt',
            '晚': 'Tard',
            '多': 'Beaucoup',
            '少': 'Peu',
            '全': 'Tout',
            '部分': 'Partiel',
            '所有': 'Tous',
            '一些': 'Quelques',
            '没有': 'Aucun',
            '每个': 'Chaque',
            '其他': 'Autre',
            '同样': 'Même',
            '不同': 'Différent',
            '相同': 'Même',
            '类似': 'Similaire',
            '相反': 'Contraire',
            '正确': 'Correct',
            '错误': 'Incorrect',
            '真': 'Vrai',
            '假': 'Faux',
            '真实': 'Réel',
            '虚拟': 'Virtuel',
            '实际': 'Pratiquement',
            '理论': 'Théoriquement',
            '可能': 'Possible',
            '不可能': 'Impossible',
            '应该': 'Devrait',
            '必须': 'Doit',
            '可以': 'Peut',
            '会': 'Va',
            '将要': 'Va',
            '曾经': 'Avait',
            '正在': 'Est en train de',
            '已经': 'A déjà',
            '还没有': 'N\'a pas encore',
            '刚刚': 'Viens de',
            '马上': 'Va',
            '立刻': 'Va tout de suite',
            '很快': 'Bientôt',
            '不久': 'Bientôt',
            '永远': 'Toujours',
            '从不': 'Jamais',
            '总是': 'Toujours',
            '经常': 'Souvent',
            '有时': 'Parfois',
            '偶尔': 'De temps en temps',
            '很少': 'Rarement',
            '几乎不': 'Presque jamais',
            '完全不': 'Pas du tout',
            '更加': 'Plus',
            '最': 'Le plus',
            '稍微': 'Un peu',
            '非常': 'Très',
            '相当': 'Assez',
            '比较': 'Plus',
            '太': 'Trop',
            '足够': 'Assez',
            '不够': 'Pas assez',
            '太多': 'Trop',
            '太少': 'Pas assez',
            '这么': 'Si',
            '那么': 'Alors',
            '多么': 'Comme',
            '怎样': 'Comment',
            '为什么': 'Pourquoi',
            '何时': 'Quand',
            '何地': 'Où',
            '何人': 'Qui',
            '何事': 'Quoi',
            '如何': 'Comment',
            '多少': 'Combien',
            '哪一个': 'Lequel',
            '哪一些': 'Quels',
            '这里': 'Ici',
            '那里': 'Là',
            '到处': 'Partout',
            '某处': 'Quelque part',
            '任何地方': 'N\'importe où',
            '没有地方': 'Nulle part',
            '现在': 'Maintenant',
            '当时': 'Alors',
            '以前': 'Avant',
            '以后': 'Après',
            '永远': 'Toujours',
            '暂时': 'Temporairement',
            '偶尔': 'De temps en temps',
            '频繁': 'Fréquemment',
            '连续': 'En continu',
            '反复': 'À plusieurs reprises',
            '一次': 'Une fois',
            '两次': 'Deux fois',
            '多次': 'Plusieurs fois',
            '再次': 'Encore',
            '重新': 'À nouveau',
            '一起': 'Ensemble',
            '单独': 'Seul',
            '分开': 'Séparément',
            '各自': 'Chacun',
            '共同': 'Ensemble',
            '互相': 'Mutuellement',
            '彼此': 'L\'un l\'autre',
            '代替': 'Au lieu de',
            '相反': 'Au contraire',
            '然而': 'Cependant',
            '但是': 'Mais',
            '虽然': 'Bien que',
            '即使': 'Même si',
            '除非': 'Sauf si',
            '如果': 'Si',
            '万一': 'Au cas où',
            '只要': 'Tant que',
            '只有': 'Seulement si',
            '无论': 'Peu importe',
            '不管': 'Quel que soit',
            '以便': 'Afin de',
            '为了': 'Pour',
            '因为': 'Parce que',
            '由于': 'Grâce à',
            '所以': 'Donc',
            '因此': 'Par conséquent',
            '总之': 'En résumé',
            '最后': 'Enfin',
            '首先': 'D\'abord',
            '其次': 'Ensuite',
            '然后': 'Puis',
            '接着': 'Après',
            '之后': 'Plus tard',
            '之前': 'Avant',
            '同时': 'En même temps',
            '当...时候': 'Quand',
            '在...之前': 'Avant que',
            '在...之后': 'Après que',
            '直到': 'Jusqu\'à ce que',
            '一...就': 'Dès que',
            '每当': 'Chaque fois que',
            '随着': 'Alors que',
            '与...相比': 'Comparé à',
            '根据': 'Selon',
            '按照': 'Suivant',
            '关于': 'Concernant',
            '对于': 'Pour',
            '至于': 'Quant à',
            '除了': 'Hormis',
            '包括': 'Incluant',
            '不包括': 'Excluant',
            '通过': 'Par',
            '用': 'Avec',
            '以': 'À',
            '从': 'De',
            '到': 'À',
            '在': 'À',
            '向': 'Vers',
            '朝': 'Vers',
            '对': 'À',
            '给': 'À',
            '为': 'Pour',
            '替': 'Pour',
            '和': 'Avec',
            '跟': 'Avec',
            '同': 'Avec',
            '与': 'Avec',
            '及': 'Et',
            '以及': 'Et',
            '还有': 'Et aussi',
            '而': 'Et',
            '并且': 'Et',
            '而': 'Mais',
            '却': 'Mais',
            '反而': 'Au lieu de',
            '倒不如': 'Mieux vaut',
            '宁可': 'Préférer',
            '与其': 'Plutôt que',
            '不如': 'Mieux vaut',
            '或者': 'Ou',
            '要么': 'Soit',
            '不是...就是': 'Soit...soit',
            '还是': 'Ou',
            '是否': 'Si',
            '无论...还是': 'Que...ou',
            '不管...还是': 'Quel que soit',
            '既...又': 'À la fois...et',
            '不仅...而且': 'Non seulement...mais aussi',
            '不但...还': 'Non seulement...mais aussi',
            '虽然...但是': 'Bien que...mais',
            '尽管...还是': 'Malgré...toujours',
            '如果...就': 'Si...alors',
            '只要...就': 'Tant que...alors',
            '只有...才': 'Seulement si...alors',
            '除非...否则': 'Sauf si...sinon',
            '因为...所以': 'Parce que...donc',
            '既然...就': 'Étant donné que...alors',
            '即使...也': 'Même si...encore',
            '无论...都': 'Peu importe...toujours',
            '不管...都': 'Quel que soit...toujours',
            '不管...还是': 'Que...ou',
            '无论...还是': 'Que...ou',
            '不是...而是': 'Ce n\'est pas...mais',
            '与其...不如': 'Plutôt que...mieux vaut',
            '宁可...也不': 'Préférer...plutôt que',
            '越...越': 'Plus...plus',
            '越来越': 'De plus en plus',
            '渐渐': 'Peu à peu',
            '逐步': 'Progressivement',
            '突然': 'Soudain',
            '忽然': 'Brusquement',
            '猛然': 'Violemment',
            '骤然': 'Subitement',
            '匆匆': 'Hâtivement',
            '慢慢': 'Lentement',
            '缓缓': 'Doucement',
            '悄悄': 'Discrètement',
            '偷偷': 'Secretement',
            '暗暗': 'En secret',
            '默默': 'Silencieusement',
            '静静': 'Quietement',
            '轻轻': 'Doucement',
            '重重': 'Lourdement',
            '狠狠': 'Violemment',
            '紧紧': 'Fortement',
            '牢牢': 'Solidement',
            '稳稳': 'Firme',
            '稳稳': 'Stable',
            '稳稳': 'Sécurisé',
        },
        'fr': {
            'Bonjour': '你好',
            'Bonsoir': '晚上好',
            'Merci': '谢谢',
            'Au revoir': '再见',
            'S\'il vous plaît': '请',
            'Désolé': '对不起',
            'Oui': '是',
            'Non': '不',
            'D\'accord': '好的',
            'Je': '我',
            'Tu': '你',
            'Vous': '你/你们',
            'Il': '他',
            'Elle': '她',
            'Nous': '我们',
            'Ils': '他们',
            'Elles': '她们',
            'Aujourd\'hui': '今天',
            'Demain': '明天',
            'Hier': '昨天',
            'Temps': '时间',
            'Travail': '工作',
            'Étude': '学习',
            'École': '学校',
            'Maison': '家',
            'Ami': '朋友',
            'Famille': '家人',
            'Amour': '爱',
            'Bonheur': '幸福',
            'Ordinateur': '计算机',
            'Traduction': '翻译',
            'Chinois': '中文',
            'Français': '法语',
            'Chine': '中国',
            'France': '法国',
            'Pékin': '北京',
            'Paris': '巴黎',
            'Comment tu t\'appelles ?': '你叫什么名字？',
            'Comment ça va ?': '你好吗？',
            'Ravi de vous rencontrer': '很高兴见到你',
            'Excusez-moi': '请问',
            'Combien ça coûte ?': '多少钱？',
            'Où est-ce ?': '在哪里？',
            'Je viens de Chine': '我来自中国',
            'J\'aime': '我喜欢',
            'Je veux': '我想要',
            'Pouvez-vous m\'aider ?': '可以帮助我吗？',
            'Ça va': '没关系',
            'Très bien': '非常好',
            'De rien': '不客气',
            'Bienvenue': '欢迎',
            'Bonjour': '早上好',
            'Bonsoir': '晚上好',
            'Au revoir': '再见',
            'Merci beaucoup': '非常感谢',
            'Merci bien': '非常感谢',
            'S\'il vous plaît': '请',
            'Je vous en prie': '不客气',
            'Pardon': '对不起',
            'Excusez-moi': '打扰一下',
            'Parlez-vous chinois ?': '你会说中文吗？',
            'Je ne parle pas français': '我不会说法语',
            'Je comprends': '我明白',
            'Je ne comprends pas': '我不明白',
            'Peux-tu répéter ?': '你能再说一遍吗？',
            'Vite': '快点',
            'Lentement': '慢慢说',
            'Je voudrais': '我想要',
            'Je dois': '我必须',
            'Je peux': '我可以',
            'Je vais': '我要去',
            'Je suis': '我是',
            'J\'ai': '我有',
            'Je suis heureux': '我很高兴',
            'Je suis triste': '我很难过',
            'Je suis fatigué': '我很累',
            'Je suis affamé': '我很饿',
            'Je suis assoiffé': '我很渴',
            'Je suis malade': '我生病了',
            'Je suis en bonne santé': '我很健康',
            'Je suis jeune': '我很年轻',
            'Je suis vieux': '我老了',
            'Je suis nouveau': '我是新来的',
            'Je suis ancien': '我是老员工',
            'C\'est bon': '很好',
            'C\'est mauvais': '很坏',
            'C\'est beau': '很美',
            'C\'est laid': '很丑',
            'C\'est propre': '很干净',
            'C\'est sale': '很脏',
            'C\'est grand': '很大',
            'C\'est petit': '很小',
            'C\'est long': '很长',
            'C\'est court': '很短',
            'C\'est haut': '很高',
            'C\'est bas': '很矮',
            'C\'est large': '很宽',
            'C\'est étroit': '很窄',
            'C\'est épais': '很厚',
            'C\'est fin': '很薄',
            'C\'est lourd': '很重',
            'C\'est léger': '很轻',
            'C\'est vite': '很快',
            'C\'est lent': '很慢',
            'C\'est tôt': '很早',
            'C\'est tard': '很晚',
            'C\'est beaucoup': '很多',
            'C\'est peu': '很少',
            'C\'est tout': '全部',
            'C\'est partiel': '部分',
            'C\'est tous': '所有',
            'C\'est quelques': '一些',
            'C\'est aucun': '没有',
            'C\'est chaque': '每个',
            'C\'est autre': '其他',
            'C\'est même': '同样',
            'C\'est différent': '不同',
            'C\'est similaire': '类似',
            'C\'est contraire': '相反',
            'C\'est correct': '正确',
            'C\'est incorrect': '错误',
            'C\'est vrai': '真',
            'C\'est faux': '假',
            'C\'est réel': '真实',
            'C\'est virtuel': '虚拟',
            'C\'est possible': '可能',
            'C\'est impossible': '不可能',
            'C\'est devrait': '应该',
            'C\'est doit': '必须',
            'C\'est peut': '可以',
            'C\'est va': '会',
            'C\'est va': '将要',
            'C\'est avait': '曾经',
            'C\'est est en train de': '正在',
            'C\'est a déjà': '已经',
            'C\'est n\'a pas encore': '还没有',
            'C\'est viens de': '刚刚',
            'C\'est va': '马上',
            'C\'est va tout de suite': '立刻',
            'C\'est bientôt': '很快',
            'C\'est toujours': '永远',
            'C\'est jamais': '从不',
            'C\'est souvent': '经常',
            'C\'est parfois': '有时',
            'C\'est de temps en temps': '偶尔',
            'C\'est rarement': '很少',
            'C\'est presque jamais': '几乎不',
            'C\'est pas du tout': '完全不',
            'C\'est plus': '更加',
            'C\'est le plus': '最',
            'C\'est un peu': '稍微',
            'C\'est très': '非常',
            'C\'est assez': '相当',
            'C\'est trop': '太',
            'C\'est pas assez': '不够',
            'C\'est si': '这么',
            'C\'est alors': '那么',
            'C\'est comme': '多么',
            'C\'est comment': '怎样',
            'C\'est pourquoi': '为什么',
            'C\'est quand': '何时',
            'C\'est où': '何地',
            'C\'est qui': '何人',
            'C\'est quoi': '何事',
            'C\'est combien': '多少',
            'C\'est lequel': '哪一个',
            'C\'est ici': '这里',
            'C\'est là': '那里',
            'C\'est partout': '到处',
            'C\'est quelque part': '某处',
            'C\'est n\'importe où': '任何地方',
            'C\'est nulle part': '没有地方',
            'C\'est maintenant': '现在',
            'C\'est alors': '当时',
            'C\'est avant': '以前',
            'C\'est après': '以后',
            'C\'est temporairement': '暂时',
            'C\'est fréquemment': '频繁',
            'C\'est en continu': '连续',
            'C\'est à plusieurs reprises': '反复',
            'C\'est une fois': '一次',
            'C\'est deux fois': '两次',
            'C\'est plusieurs fois': '多次',
            'C\'est encore': '再次',
            'C\'est à nouveau': '重新',
            'C\'est ensemble': '一起',
            'C\'est seul': '单独',
            'C\'est séparément': '分开',
            'C\'est chacun': '各自',
            'C\'est mutuellement': '互相',
            'C\'est l\'un l\'autre': '彼此',
            'C\'est au lieu de': '代替',
            'C\'est au contraire': '相反',
            'C\'est cependant': '然而',
            'C\'est mais': '但是',
            'C\'est bien que': '虽然',
            'C\'est même si': '即使',
            'C\'est sauf si': '除非',
            'C\'est si': '如果',
            'C\'est au cas où': '万一',
            'C\'est tant que': '只要',
            'C\'est seulement si': '只有',
            'C\'est peu importe': '无论',
            'C\'est quel que soit': '不管',
            'C\'est afin de': '以便',
            'C\'est pour': '为了',
            'C\'est parce que': '因为',
            'C\'est grâce à': '由于',
            'C\'est donc': '所以',
            'C\'est par conséquent': '因此',
            'C\'est en résumé': '总之',
            'C\'est enfin': '最后',
            'C\'est d\'abord': '首先',
            'C\'est ensuite': '其次',
            'C\'est puis': '然后',
            'C\'est après': '接着',
            'C\'est plus tard': '之后',
            'C\'est avant': '之前',
            'C\'est en même temps': '同时',
            'C\'est quand': '当...时候',
            'C\'est avant que': '在...之前',
            'C\'est après que': '在...之后',
            'C\'est jusqu\'à ce que': '直到',
            'C\'est dès que': '一...就',
            'C\'est chaque fois que': '每当',
            'C\'est alors que': '随着',
            'C\'est comparé à': '与...相比',
            'C\'est selon': '根据',
            'C\'est suivant': '按照',
            'C\'est concernant': '关于',
            'C\'est pour': '对于',
            'C\'est quant à': '至于',
            'C\'est hormis': '除了',
            'C\'est incluant': '包括',
            'C\'est excluant': '不包括',
            'C\'est par': '通过',
            'C\'est avec': '用',
            'C\'est à': '以',
            'C\'est de': '从',
            'C\'est vers': '向',
            'C\'est avec': '和',
            'C\'est et': '并且',
            'C\'est mais': '却',
            'C\'est ou': '或者',
            'C\'est soit': '要么',
            'C\'est si': '是否',
            'C\'est que': '无论',
            'C\'est à la fois': '既...又',
            'C\'est non seulement': '不仅...而且',
            'C\'est bien que': '虽然...但是',
            'C\'est si': '如果...就',
            'C\'est tant que': '只要...就',
            'C\'est seulement si': '只有...才',
            'C\'est parce que': '因为...所以',
            'C\'est même si': '即使...也',
            'C\'est peu importe': '无论...都',
            'C\'est ce n\'est pas': '不是...而是',
            'C\'est plutôt que': '与其...不如',
            'C\'est préférer': '宁可...也不',
            'C\'est plus': '越...越',
            'C\'est de plus en plus': '越来越',
            'C\'est peu à peu': '渐渐',
            'C\'est progressivement': '逐步',
            'C\'est soudain': '突然',
            'C\'est brusquement': '忽然',
            'C\'est violemment': '猛然',
            'C\'est subitement': '骤然',
            'C\'est hâtivement': '匆匆',
            'C\'est lentement': '慢慢',
            'C\'est doucement': '缓缓',
            'C\'est discrètement': '悄悄',
            'C\'est secretement': '偷偷',
            'C\'est en secret': '暗暗',
            'C\'est silencieusement': '默默',
            'C\'est quietement': '静静',
            'C\'est doucement': '轻轻',
            'C\'est lourdement': '重重',
            'C\'est violemment': '狠狠',
            'C\'est fortement': '紧紧',
            'C\'est solidement': '牢牢',
            'C\'est firme': '稳稳',
        }
    }
    
    phrases = common_phrases.get(source_lang, {})
    translated_text = text
    
    for original, translated in phrases.items():
        translated_text = translated_text.replace(original, translated)
    
    if terminology_hint:
        terms = terminology_hint.split(', ')
        for term in terms:
            if '=' in term:
                parts = term.split('=', 1)
                if source_lang == 'zh':
                    original_term = parts[0].strip()
                    target_term = parts[1].strip()
                    translated_text = translated_text.replace(original_term, target_term)
                else:
                    original_term = parts[0].strip()
                    target_term = parts[1].strip()
                    translated_text = translated_text.replace(original_term, target_term)
    
    return translated_text

@app.post("/api/translate")
async def translate(request: TranslateRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="翻译文本不能为空")
    
    memory_result = get_memory_by_text(request.text.strip(), request.source_lang)
    if memory_result:
        target_text, target_lang, similarity = memory_result
        is_exact = similarity >= 1.0
        return {
            "success": True,
            "result": target_text,
            "from_memory": True,
            "is_exact_match": is_exact,
            "similarity": round(similarity, 2),
            "used_terminology": []
        }
    
    matching_terms = find_matching_terms(request.text, request.source_lang)
    terminology_hint = ", ".join(matching_terms) if matching_terms else ""
    
    if request.api_service != "free" and request.api_key:
        try:
            translated_text = call_paid_api(
                request.text,
                request.source_lang,
                request.target_lang,
                request.api_key,
                request.api_service,
                request.model,
                "",
                terminology_hint
            )
        except Exception as paid_error:
            print(f"付费API调用失败，自动降级到免费服务: {str(paid_error)}")
            translated_text = call_translation_api(
                request.text,
                request.source_lang,
                request.target_lang,
                request.api_key,
                request.api_service,
                request.model,
                terminology_hint
            )
    else:
        translated_text = call_translation_api(
            request.text,
            request.source_lang,
            request.target_lang,
            request.api_key,
            request.api_service,
            request.model,
            terminology_hint
        )
    
    add_memory(request.text, request.source_lang, translated_text, request.target_lang)

    return {
        "success": True,
        "result": translated_text,
        "from_memory": False,
        "is_exact_match": False,
        "similarity": 0.0,
        "used_terminology": matching_terms
    }

@app.get("/api/memory")
async def get_memory():
    memories = get_all_memories()
    return {"success": True, "data": memories}

@app.delete("/api/memory/{memory_id}")
async def delete_memory_by_id(memory_id: int):
    success = delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆记录不存在")
    return {"success": True}

@app.delete("/api/memory")
async def clear_memory():
    clear_all_memories()
    return {"success": True}

@app.get("/api/terminology")
async def get_terminology():
    terms = get_all_terminology()
    return {"success": True, "data": terms}

@app.post("/api/terminology/import")
async def import_terminology(request: ImportTermsRequest):
    for term in request.terms:
        if "chinese_term" in term and "french_term" in term:
            add_terminology(term["chinese_term"], term["french_term"])
    return {"success": True, "count": len(request.terms)}

@app.post("/api/terminology/upload")
async def upload_terminology(file: UploadFile = File(...)):
    content = await file.read()
    rows = []
    
    if file.filename.endswith('.csv'):
        reader = csv.reader(io.StringIO(content.decode('utf-8')))
        for row in reader:
            if len(row) >= 2:
                rows.append([row[0].strip(), row[1].strip()])
    elif file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                if len(row) >= 2:
                    rows.append([str(row[0]).strip() if row[0] else '', str(row[1]).strip() if row[1] else ''])
        except ImportError:
            raise HTTPException(status_code=400, detail="需要安装openpyxl库来处理Excel文件")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传CSV或Excel文件")
    
    if not rows:
        raise HTTPException(status_code=400, detail="文件中没有有效的数据")
    
    count = 0
    for chinese, french in rows:
        if chinese and french and chinese != 'None' and french != 'None':
            add_terminology(chinese, french)
            count += 1
    
    return {"success": True, "count": count}

@app.delete("/api/terminology/{term_id}")
async def delete_term(term_id: int):
    success = delete_terminology(term_id)
    if not success:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {"success": True}

@app.delete("/api/terminology")
async def clear_terminology():
    clear_all_terminology()
    return {"success": True}

@app.post("/api/transcribe")
async def transcribe(request: TranscribeRequest):
    if not request.text.strip():
        return {"success": False, "result": ""}
    
    memory_result = get_memory_by_text(request.text.strip(), request.source_lang)
    if memory_result:
        return {
            "success": True,
            "result": memory_result[0],
            "from_memory": True
        }
    
    matching_terms = find_matching_terms(request.text, request.source_lang)
    terminology_hint = ", ".join(matching_terms) if matching_terms else ""
    
    translated_text = call_translation_api(
        request.text,
        request.source_lang,
        request.target_lang,
        request.api_key,
        request.api_service,
        "free",
        terminology_hint
    )
    
    add_memory(request.text, request.source_lang, translated_text, request.target_lang)
    
    return {
        "success": True,
        "result": translated_text,
        "from_memory": False
    }

@app.post("/api/document/translate")
async def translate_document(file: UploadFile = File(...), source_lang: str = "zh", target_lang: str = "fr", api_key: str = "", api_service: str = "free", model: str = "free"):
    filename = file.filename.lower()
    content = await file.read()
    
    if filename.endswith('.txt'):
        text = content.decode('utf-8')
    elif filename.endswith('.csv'):
        reader = csv.reader(io.StringIO(content.decode('utf-8')))
        text = '\n'.join([','.join(row) for row in reader])
    elif filename.endswith('.xlsx') or filename.endswith('.xls'):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), read_only=True)
            ws = wb.active
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append([str(cell) if cell else '' for cell in row])
            text = '\n'.join(['\t'.join(row) for row in rows])
        except ImportError:
            raise HTTPException(status_code=400, detail="需要安装openpyxl库来处理Excel文件")
    elif filename.endswith('.docx') or filename.endswith('.doc'):
        try:
            text = extract_text_from_docx(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Word文档解析失败: {str(e)}")
    elif filename.endswith('.pptx') or filename.endswith('.ppt'):
        try:
            text = extract_text_from_pptx(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PPT文档解析失败: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传TXT、CSV、Excel、Word或PPT文件")
    
    paragraphs = segment_text(text, source_lang)
    
    translated_paragraphs = []
    total_sentences = 0
    translated_sentences = 0
    
    for para in paragraphs:
        translated_sentences_list = []
        
        for sentence in para['sentences']:
            total_sentences += 1
            
            memory_result = get_memory_by_text(sentence, source_lang)
            if memory_result:
                translated_sentences_list.append(memory_result[0])
                translated_sentences += 1
                continue
            
            matching_terms = find_matching_terms(sentence, source_lang)
            terminology_hint = ", ".join(matching_terms) if matching_terms else ""
            
            try:
                if api_service != "free" and api_key:
                    try:
                        translated = call_paid_api(
                            sentence, source_lang, target_lang,
                            api_key, api_service, model, "", terminology_hint
                        )
                    except Exception as paid_error:
                        print(f"付费API调用失败，自动降级到免费服务: {str(paid_error)}")
                        translated = call_translation_api(
                            sentence, source_lang, target_lang,
                            api_key, api_service, model, terminology_hint
                        )
                else:
                    translated = call_translation_api(
                        sentence, source_lang, target_lang,
                        api_key, api_service, model, terminology_hint
                    )
                
                add_memory(sentence, source_lang, translated, target_lang)
                translated_sentences_list.append(translated)
                translated_sentences += 1
            except Exception as e:
                translated_sentences_list.append(f"[翻译失败: {str(e)}]")
        
        translated_paragraphs.append({
            "original": para['text'],
            "translated": "\n".join(translated_sentences_list),
            "sentences_count": len(para['sentences'])
        })
    
    full_translation = "\n\n".join([p['translated'] for p in translated_paragraphs])
    
    return {
        "success": True,
        "filename": file.filename,
        "paragraphs": translated_paragraphs,
        "full_translation": full_translation,
        "stats": {
            "total_sentences": total_sentences,
            "translated_sentences": translated_sentences
        }
    }

@app.get("/api/export")
async def export_translations():
    memories = get_all_memories()
    
    export_data = []
    for m in memories:
        export_data.append({
            "id": m['id'],
            "source_text": m['source_text'],
            "target_text": m['target_text'],
            "source_lang": m['source_lang'],
            "target_lang": m['target_lang'],
            "created_at": m['created_at']
        })
    
    return {"success": True, "data": export_data}

@app.get("/api/export/txt")
async def export_translations_txt():
    memories = get_all_memories()
    
    content = "=== 中法翻译记录导出 ===\n\n"
    content += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"总记录数: {len(memories)}\n\n"
    content += "=" * 50 + "\n\n"
    
    for i, m in enumerate(memories, 1):
        direction = "中文→法语" if m['source_lang'] == 'zh' else "法语→中文"
        content += f"[{i}] {direction}\n"
        content += f"原文: {m['source_text']}\n"
        content += f"译文: {m['target_text']}\n"
        content += f"时间: {m['created_at']}\n"
        content += "-" * 30 + "\n\n"
    
    return Response(
        content=content.encode('utf-8'),
        media_type='text/plain',
        headers={
            'Content-Disposition': 'attachment; filename="translation_export.txt"'
        }
    )

class ExportSingleRequest(BaseModel):
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str

@app.post("/api/export/single")
async def export_single_translation(request: ExportSingleRequest):
    direction = "中文→法语" if request.source_lang == 'zh' else "法语→中文"
    
    content = "=== 中法翻译结果导出 ===\n\n"
    content += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"翻译方向: {direction}\n\n"
    content += "=" * 50 + "\n\n"
    content += f"原文:\n{request.source_text}\n\n"
    content += "-" * 50 + "\n\n"
    content += f"译文:\n{request.target_text}\n"
    
    return Response(
        content=content.encode('utf-8'),
        media_type='text/plain',
        headers={
            'Content-Disposition': 'attachment; filename="current_translation.txt"'
        }
    )

@app.get("/api/vocabulary")
async def get_vocabulary(unmastered_only: bool = False):
    if unmastered_only:
        vocab = get_unmastered_vocabulary()
    else:
        vocab = get_all_vocabulary()
    return {"success": True, "data": vocab}

@app.put("/api/vocabulary/{vocab_id}")
async def update_vocab(vocab_id: int, request: VocabularyUpdateRequest):
    success = update_vocabulary_mastered(vocab_id, request.mastered)
    if not success:
        raise HTTPException(status_code=404, detail="生词不存在")
    return {"success": True}

@app.delete("/api/vocabulary/{vocab_id}")
async def delete_vocab(vocab_id: int):
    success = delete_vocabulary(vocab_id)
    if not success:
        raise HTTPException(status_code=404, detail="生词不存在")
    return {"success": True}

@app.delete("/api/vocabulary")
async def clear_vocabulary():
    clear_all_vocabulary()
    return {"success": True}

@app.post("/api/vocabulary/add")
async def add_vocab(request: dict):
    if "source_word" not in request or "target_word" not in request:
        raise HTTPException(status_code=400, detail="缺少必要参数")

    source_word = request["source_word"]
    source_lang = request.get("source_lang", "fr")
    target_word = request["target_word"]
    target_lang = request.get("target_lang", "zh")

    # 生成例句
    example_sentence = ""
    try:
        if source_lang == 'fr':
            cn_example = f"这个词的意思是{target_word}。"
            fr_example = translate_with_google_direct(cn_example, 'zh', 'fr')
            example_sentence = f"法语：{source_word}\n例句：{fr_example}\n中文：{cn_example}"
        else:
            cn_example = f"我学到了一个新词{source_word}。"
            fr_example = translate_with_google_direct(cn_example, 'zh', 'fr')
            example_sentence = f"中文：{source_word}\n例句：{cn_example}\n法语：{fr_example}"
    except:
        example_sentence = ""

    add_vocabulary(
        source_word, source_lang, target_word, target_lang,
        request.get("context", ""), example_sentence
    )
    return {"success": True, "example_sentence": example_sentence}


class GenerateExampleRequest(BaseModel):
    source_word: str
    source_lang: str
    target_word: str

@app.post("/api/vocabulary/generate-example")
async def generate_example(request: GenerateExampleRequest):
    try:
        if request.source_lang == 'fr':
            cn_example = f"这是一个{request.target_word}的例子。"
            fr_example = translate_with_google_direct(cn_example, 'zh', 'fr')
            example = f"法语：{request.source_word}\n例句：{fr_example}\n中文：{cn_example}"
        else:
            cn_example = f"这是一个包含{request.source_word}的例句。"
            fr_example = translate_with_google_direct(cn_example, 'zh', 'fr')
            example = f"中文：{request.source_word}\n例句：{cn_example}\n法语：{fr_example}"
        return {"success": True, "example": example}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成例句失败: {str(e)}")


class EditVocabRequest(BaseModel):
    source_word: str = None
    target_word: str = None
    example_sentence: str = None

@app.put("/api/vocabulary/{vocab_id}/edit")
async def edit_vocabulary(vocab_id: int, request: EditVocabRequest):
    success = update_vocabulary(vocab_id, request.source_word, request.target_word, request.example_sentence)
    if not success:
        raise HTTPException(status_code=404, detail="生词不存在")
    return {"success": True}


class AddMeaningRequest(BaseModel):
    new_meaning: str

@app.post("/api/vocabulary/{vocab_id}/meaning")
async def add_meaning(vocab_id: int, request: AddMeaningRequest):
    success = add_vocabulary_meaning(vocab_id, request.new_meaning)
    if not success:
        raise HTTPException(status_code=404, detail="生词不存在")
    return {"success": True}


class ValidateTranslationRequest(BaseModel):
    source_text: str
    user_translation: str
    source_lang: str
    target_lang: str

@app.post("/api/translation/validate")
async def validate_translation(request: ValidateTranslationRequest):
    # 用翻译引擎重新翻译
    try:
        engine_translation = call_translation_api(
            request.source_text, request.source_lang, request.target_lang,
            "", "free", "free", ""
        )
    except:
        engine_translation = ""

    # 简单对比：计算相似度
    if not engine_translation:
        return {"success": True, "valid": True, "message": "无法自动校验，已保留您的修改", "engine_translation": ""}

    # 计算字符级相似度
    user_chars = set(request.user_translation.strip())
    engine_chars = set(engine_translation.strip())
    if len(user_chars) == 0 and len(engine_chars) == 0:
        similarity = 1.0
    elif len(user_chars) == 0 or len(engine_chars) == 0:
        similarity = 0.0
    else:
        common = user_chars & engine_chars
        similarity = len(common) / max(len(user_chars), len(engine_chars))

    if similarity >= 0.5:
        return {"success": True, "valid": True, "message": "修改看起来没问题，已保留", "engine_translation": engine_translation, "similarity": round(similarity, 2)}
    else:
        return {"success": True, "valid": False, "message": "您的修改与机器翻译差异较大，请检查是否有误", "engine_translation": engine_translation, "similarity": round(similarity, 2)}


class ExportDocumentRequest(BaseModel):
    filename: str = "document"
    paragraphs: list[dict]

@app.post("/api/document/export")
async def export_document(request: ExportDocumentRequest):
    content = f"=== 文档翻译对照导出 ===\n\n"
    content += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"段落数: {len(request.paragraphs)}\n\n"
    content += "=" * 60 + "\n\n"

    for i, p in enumerate(request.paragraphs, 1):
        content += f"【段落 {i}】\n"
        content += f"原文：\n{p.get('original', '')}\n\n"
        content += f"译文：\n{p.get('translated', '')}\n\n"
        content += "-" * 60 + "\n\n"

    return Response(
        content=content.encode('utf-8'),
        media_type='text/plain',
        headers={
            'Content-Disposition': f'attachment; filename="document_translation.txt"'
        }
    )

frontend_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"message": "中法互译工具 API", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)