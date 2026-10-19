import cv2
import os
import json
import datetime
from PIL import Image
from Katna.video import Video
from Katna.writer import KeyFrameDiskWriter
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import openai
import base64
import torch
import clip
import numpy as np
import time
import re
# This code is provisional due to an error in the summary

def is_valid_summary(summary_text):
    """
    Verifies if the summary is valid (not empty, not just dashes, etc.)
    """
    if not summary_text or not summary_text.strip():
        return False
    
    # Remove whitespace and line breaks
    cleaned_text = summary_text.strip()
    
    # Verify if it only contains dashes, asterisks, or special characters
    if re.match(r'^[\s\-_*]+$', cleaned_text):
        return False
    
    # Verify if it's too short (less than 10 characters)
    if len(cleaned_text) < 10:
        return False
    
    # Verify if it contains only symbols or non-alphabetic characters
    if not re.search(r'[a-zA-Z]', cleaned_text):
        return False
    
    # Verify if it appears to be a common API error
    error_patterns = [
        "error",
        "could not",
        "cannot",
        "impossible",
        "failed",
        "empty",
        "no content",
        "unable to",
        "failed to generate"
    ]
    
    cleaned_lower = cleaned_text.lower()
    for pattern in error_patterns:
        if pattern in cleaned_lower:
            return False
    
    return True


def extract_keyframes(video_path, output_folder="keyframes"):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    if frame_rate == 0:
        print("Error: Could not get frame rate from video.")
        return [], 0
    video_duration = total_frames / frame_rate
    frame_interval = max(1, total_frames // 100)
    frames = []
    frame_indices = []
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, i))
        frame_indices.append(i)
    cap.release()
    if not frames:
        return [], video_duration
    frames_tensor = torch.cat([f[0] for f in frames])
    with torch.no_grad():
        image_features = model.encode_image(frames_tensor)
    image_features /= image_features.norm(dim=-1, keepdim=True)
    similarities = torch.mm(image_features, image_features.T)
    diversity_scores = similarities.sum(dim=1)
    num_keyframes = max(5, min(len(frames) // 10, 15))
    keyframe_indices = torch.argsort(diversity_scores)[:num_keyframes]
    selected_frames = [frames[idx] for idx in keyframe_indices.cpu().numpy()]
    selected_frames.sort(key=lambda x: x[2])
    os.makedirs(output_folder, exist_ok=True)
    keyframes_json = []
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        frame_time = frame_num / frame_rate
        keyframes_json.append({
            "frame_index": idx,
            "frame_number": frame_num,
            "timestamp": frame_time,
            "filename": f"keyframe_{frame_num}.jpg"
        })
    json_path = os.path.join(output_folder, "keyframes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(keyframes_json, f, ensure_ascii=False, indent=2)
    return [frame[2] for frame in selected_frames], video_duration

def extract_keyframes_clip_adjustable(video_path, output_folder="keyframes_clip", 
                                    diversity_threshold=0.7, 
                                    similarity_threshold=0.8,
                                    min_keyframes=5, 
                                    max_keyframes=15,
                                    frame_sampling_rate=30):
    """
    Extrae keyframes usando CLIP con umbrales ajustables
    """
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)
    
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_rate = cap.get(cv2.CAP_PROP_FPS)
    
    if frame_rate == 0:
        print("Error: Could not get frame rate from video.")
        return [], 0
    
    video_duration = total_frames / frame_rate
    
    # Ajustar intervalo de muestreo
    frame_interval = max(1, frame_sampling_rate)
    
    frames = []
    frame_indices = []
    
    print(f"Analyzing video with {total_frames} frames, sampling every {frame_interval} frames...")
    
    for i in range(0, total_frames, frame_interval):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = preprocess(Image.fromarray(frame_rgb)).unsqueeze(0).to(device)
        frames.append((image, frame_rgb, i))
        frame_indices.append(i)
    
    cap.release()
    
    if not frames:
        return [], video_duration
    
    # Extraer características CLIP
    frames_tensor = torch.cat([f[0] for f in frames])
    with torch.no_grad():
        image_features = model.encode_image(frames_tensor)
    
    image_features /= image_features.norm(dim=-1, keepdim=True)
    similarities = torch.mm(image_features, image_features.T)
    
    # Selección por diversidad
    diversity_scores = similarities.sum(dim=1)
    diversity_scores = (diversity_scores - diversity_scores.min()) / (diversity_scores.max() - diversity_scores.min())
    
    # Lógica mejorada - calcular target_frames de manera más inteligente
    # Queremos extraer más frames, no solo el mínimo
    if len(frames) <= min_keyframes:
        target_frames = len(frames)
    else:
        # Tomar al menos min_keyframes, pero preferiblemente más
        # Usar una fracción más grande del total de frames
        target_frames = min(max_keyframes, max(min_keyframes, len(frames) // 2))
    
    print(f"Sampled frames: {len(frames)}, Target frames: {target_frames}")
    
    # Tomar los frames más diversos directamente
    diverse_indices = torch.argsort(diversity_scores)[:target_frames]
    
    # Usar directamente todos los frames seleccionados por diversidad
    final_keyframes = diverse_indices.tolist()
    
    # Asegurar mínimo de keyframes - lógica simplificada
    if len(final_keyframes) < min_keyframes and len(frames) >= min_keyframes:
        # Si no tenemos suficientes, tomar más frames directamente
        additional_needed = min_keyframes - len(final_keyframes)
        remaining_indices = [i for i in range(len(frames)) if i not in final_keyframes]
        if remaining_indices:
            # Tomar los frames restantes más diversos
            remaining_diversity = diversity_scores[remaining_indices]
            best_remaining = torch.argsort(remaining_diversity)[:additional_needed]
            for idx in best_remaining:
                final_keyframes.append(remaining_indices[idx.item()])
    
    # Ordenar por orden temporal
    final_keyframes.sort()
    
    selected_frames = [frames[idx] for idx in final_keyframes]
    
    # Guardar keyframes
    os.makedirs(output_folder, exist_ok=True)
    saved_frames = []
    
    # Crear JSON con información de keyframes
    keyframes_json = []
    
    for idx, (_, frame, frame_num) in enumerate(selected_frames):
        frame_path = os.path.join(output_folder, f"keyframe_{frame_num}.jpg")
        Image.fromarray(frame).save(frame_path, format="JPEG", quality=95)
        saved_frames.append(frame_num)
        
        # Agregar información al JSON
        frame_time = frame_num / frame_rate
        keyframes_json.append({
            "frame_index": idx,
            "frame_number": frame_num,
            "timestamp": frame_time,
            "filename": f"keyframe_{frame_num}.jpg"
        })
        
        print(f"Keyframe saved: keyframe_{frame_num}.jpg")
    
    # Guardar JSON con información de keyframes
    json_path = os.path.join(output_folder, "keyframes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(keyframes_json, f, ensure_ascii=False, indent=2)
    
    print(f"Total keyframes extracted with CLIP: {len(saved_frames)}")
    print(f"Configuration used - Diversity: {diversity_threshold}, Similarity: {similarity_threshold}")
    
    return saved_frames, video_duration


def generate_audiodescriptions(api_key, image_folder, output_json="audiodescriptions.json", video_duration=None):
    openai.api_key = api_key
    if video_duration is None:
        max_chars = 30
    else:
        max_chars = int(video_duration * 30)
    descriptions = []
    total_tokens = 0
    prompt = (
        f"Role: You are an Audio Description Specialist for blind or visually impaired people.\n"
        f"Task: Generate a description of the image and generate prosody based on prosodic modeling (Intensity, Tone, Duration, Rhythm)\n"
        f"Essential elements to cover:\n"
        f"- [Who] Identify characters, distinctive features and actions\n"
        f"- [What] Describe objects, events and relevant interactions\n"
        f"- [Where] Provide context of the environment\n"
        f"- [When] Indicate time of day if relevant\n"
        f"- [Action] Specify significant movements\n"
        f"- [Scene Changes] Indicate important temporal transitions\n"
        f"- [Logos] If there are logos, symbols or identifying graphic elements, describe them in detail, including their shape, predominant colors, location in the image and any relevant visual element. Explain their possible function or meaning in the scene.\n\n"

        f"Attention Mechanisms (prioritize the most relevant according to content):\n"
        f" 1. Characters:\n"
        f" Conceptual definition: Narrative entities with their own identity that participate in the action, carry physical, psychological, social and emotional traits, and whose presence has semantic weight in the construction of the narrative. Their description should prioritize attributes relevant to the plot and aspects that mark their emotional evolution. In audio description, emphasis is on functional and affective characterization.\n"
        f" Example: A young man with worn clothes and an evasive gaze walks through the train station without apparent direction. His characterization conveys anticipation (medium: anxiety), marking an emotionally suspended identity between waiting and uncertainty.\n"
        f" Characteristics:\n"
        f"   - Gender and approximate age\n"
        f"   - Real or animated\n"
        f"   - Distinctive accessories\n"
        f"   - Notable facial features\n"
        f"   - Justification: Specify WHICH character and WHAT specific aspects are relevant, explaining why\n"
        f" 2. Facial Expressions:\n"
        f" Conceptual definition: Muscular configurations of the face that communicate emotions, intentions or internal reactions of characters. They are fundamental for the emotional reading of the scene and, from a semantic perspective, function as iconic signs that connect the character's interiority with the viewer. Audio description must translate these expressions in terms that evoke the intensity and emotional quality precisely.\n"
        f" Example: A narrow hallway, with cracked walls and a flickering light at the end, accompanied by an almost imperceptible hum with a strong smell of death. The composition of the setting and atmosphere evokes an emotion of fear (high: terror), preparing the listener for a possible threat or unexpected event.\n"
        f" Characteristics:\n"
        f"   - Emotions (Joy (Low: Serenity, High: Ecstasy), Trust (Low: Acceptance, High: Admiration), Fear (Low: Apprehension, High: Terror), Surprise (Low: Distraction, High: Amazement), Sadness (Low: Grief, High: Deep Thought), Disgust (Low: Boredom, High: Hatred), Anger (Low: Annoyance, High: Fury), Anticipation (Low: Interest, High: Vigilance).)\n"
        f"   - Justification: Specify WHICH muscular configurations of the face communicate emotions and WHAT specific emotion, explaining their impact\n"
        f" 3. Actions:\n"
        f" Conceptual definition: Set of movements, gestures or behaviors executed by characters or elements in the scene that drive narrative development or communicate intentions, emotions or state changes. From the semantic dimension, actions are minimal units of meaning that articulate the logic of events, and their mention in audio description should emphasize what is relevant for the narrative and emotional understanding of the content.\n"
        f" Example: A woman slowly opens a letter, reads it and drops her arms. The action communicates an emotion of sadness (medium: sadness). The pause in movement and bodily descent are key to expressing the emotional weight of the read content.\n"
        f" Characteristics:\n"
        f"   - Character movements\n"
        f"   - Relevant object movements\n"
        f"   - Justification: Specify WHAT specific action and WHAT is its specific importance in the scene\n"
        f" 4. Settings, climate and atmosphere:\n"
        f" Conceptual definition: Articulated set by the represented physical space (setting) and the sensory and affective charge that permeates it (climate and atmosphere), which together configure the emotional and symbolic background of the narrative action. From the semantic dimension, this category covers both the material elements of the environment (architecture, objects, lighting, spatial distribution) and their expressive qualities (emotional tonality, environmental tension, perceptual rhythm). In audio description, its translation should prioritize the sensory aspects that model the viewer's emotional experience, activating emotions such as fear, joy or sadness, and facilitating the listener's narrative immersion.\n"
        f" Example: A narrow hallway, with cracked walls and a flickering light at the end, accompanied by an almost imperceptible hum with a strong smell of death. The composition of the setting and atmosphere evokes an emotion of fear (high: terror), preparing the listener for a possible threat or unexpected event.\n"
        f" Characteristics:\n"
        f"   - Location and setting\n"
        f"   - Predominant colors\n"
        f"   - Temporality\n"
        f"   - Environmental conditions\n"
        f"   - General atmosphere\n"
        f"   - Justification: Specify WHAT specific elements are relevant and WHAT is their specific importance in the scene\n"
        f" 5. Posture and Body Language:\n"
        f" Conceptual definition: Physical configurations of the body and their non-verbal movements that express emotional states, attitudinal dispositions or interpersonal relationships. They act as visual signs of emotional and contextual significance. In audio description, they must be translated into verbal images that allow inferring the emotional state, intention or narrative tension of the scene.\n"
        f" Example: A woman stands upright, with her arms crossed and her head slightly tilted back while listening to her interlocutor. Her posture indicates rejection (low: boredom), marking emotional distance and negative judgment.\n"
        f" Characteristics:\n"
        f"   - Significant gestures\n"
        f"   - Relevant postures\n"
        f"   - Justification: Specify WHAT specific gesture or posture and WHAT is its concrete meaning\n"
        f" 6. Interactions:\n"
        f" Conceptual definition: Dynamic relationships between characters or between characters and objects/environments, which reveal affective, social or symbolic bonds. Interactions are key to understanding roles, hierarchies, conflicts or alliances in the narrative universe. In audio description, not only the acts should be described, but also the relational and emotional character of the same.\n"
        f" Example: A girl leans on her grandmother's shoulder while both look at a photo album. The interaction suggests trust (low: approval), communicating an intimate and warm relationship between generations.\n"
        f" Characteristics:\n"
        f"   - Non-verbal communication between characters\n"
        f"   - Justification: Specify WHICH characters interact and WHAT they specifically communicate\n"
        f" 7. Special Effects:\n"
        f" Conceptual definition: Visual, sound or digital elements that do not correspond to a mimetic representation of reality, but introduce a spectacular, symbolic or fantastic dimension in the scene. Their semantic function can reinforce emotions, emphasize actions or create transitions. In audio description, special effects must be interpreted in terms of their emotional and narrative impact, not just technical.\n"
        f" Example: A blue light explosion runs through the sky when two characters hold hands. This special effect underlines an emotion of joy (high: ecstasy), accentuating the intense emotional union between the characters.\n"
        f" Characteristics:\n"
        f"   - Relevant artificial visual elements\n"
        f"   - Justification: Specify WHAT specific effect and WHAT is its concrete purpose in the narrative\n"
        f" 8. Logos and Identifying Graphic Elements:\n"
        f" Conceptual definition: Images, symbols, logos or visual marks that identify a company, organization, product or specific content. Their presence can provide information about authorship, commercial context or communicative intentionality of the scene. In audio description, they should be described in terms of their shape, colors, location and any distinctive element, avoiding reading texts but transmitting their function or visual impact.\n"
        f" Example: In the center of the image, a blue and white logo shows the silhouette of a cameraman next to an old camera, framed by a light blue rectangle. The design conveys professionalism and is associated with an audiovisual production company.\n"
        f" Characteristics:\n"
        f"   - Shape and visual composition\n"
        f"   - Predominant colors\n"
        f"   - Location in the image\n"
        f"   - Distinctive graphic elements\n"
        f"   - Justification: Specify WHAT logo or symbol is described and WHAT is its relevance or function in the scene\n\n"

        f"For each description, indicate which attention mechanisms were used, specifying WHICH or WHAT specific element is being described and providing a detailed justification of its relevance in the scene.\n\n"
        f"Mandatory guidelines:\n"
        f"- Use present tense and active voice\n"
        f"- DO NOT mention texts, credits or written elements\n"
        f"- Describe from general to specific\n"
        f"- Maintain an objective and neutral tone\n"
        f"- Use complete sentences and clear vocabulary\n"
        f"- Be concise, avoiding unnecessary details\n"
        f"- At the end of the description, list the attention mechanisms used"
    )
    
    # Get list of files and sort them by frame number
    image_files = []
    for filename in os.listdir(image_folder):
        if filename.endswith((".jpg", ".jpeg", ".png")) and (
            filename.startswith("keyframe_")
        ):
            try:
                frame_num = int(filename.split('_')[1].split('.')[0])
                image_files.append((frame_num, filename))
            except:
                continue
    
    # Sort files by frame number
    image_files.sort(key=lambda x: x[0])
    
    # Process files in order
    for frame_num, filename in image_files:
        print(f"Processing file: {filename}")
        image_path = os.path.join(image_folder, filename)
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": "Describe this image:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
        
        full_response = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        # Separate description from attention mechanisms
        description = ""
        attention_mechanisms = ""
        
        if "Attention mechanisms" in full_response:
            parts = full_response.split("Attention mechanisms")
            description = parts[0].strip()
            attention_mechanisms = "Attention mechanisms" + parts[1].strip()
        else:
            description = full_response.strip()
        
        descriptions.append({
            "frame_number": frame_num,
            "filename": filename,
            "description": description,
            "attention_mechanisms": attention_mechanisms,
            "tokens_used": tokens_used
        })
        
        total_tokens += tokens_used
        print(f"Processed: {filename} - Tokens used: {tokens_used}")
    
    if not descriptions:
        print(f"WARNING: No images found to process in {image_folder}")
        print(f"Files found: {os.listdir(image_folder)}")
    
    print(f"Total tokens used: {total_tokens}")
    
    # Save JSON file
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, ensure_ascii=False, indent=2)
    
    print("Audio descriptions saved in", output_json)
    return descriptions

def summarize_audiodescriptions(api_key, descriptions_json, video_duration, prosody_analysis_json, output_json="video_summary.json"):
    openai.api_key = api_key
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    # Usar solo las descripciones, no los mecanismos de atención
    combined_text = " ".join([d["description"] for d in descriptions])
    
    with open(prosody_analysis_json, "r", encoding="utf-8") as f:
        prosody_content = json.load(f)
    selected_emotion = prosody_content.get("complementary_emotion", None)
    
    emotion_ranges = {
        "Grief": (6.0, 10.0),
        "Distraction": (6.5, 10.5),
        "Amazement": (7.5, 12.0),
        "Aversion": (7.0, 11.5),
        "Acceptance": (8.0, 12.5),
        "Admiration": (7.5, 12.0),
        "Apprehension": (6.5, 10.5),
        "Vigilance": (8.0, 12.5),
        "Boredom": (7.5, 12.0),
        "Deep Thought": (6.0, 10.0),
        "Deep thought": (6.0, 10.0),  # Add variation
        "Annoyance": (8.5, 13.5),
        "Serenity": (8.0, 12.5),
        "Terror": (7.5, 12.0),
        "Interest": (7.0, 11.5),
        "Ecstasy": (8.5, 13.5),
        "Fury": (8.0, 12.5)
    }
    
    # Calcular rangos de caracteres con valores por defecto si la emoción no se encuentra
    if selected_emotion and selected_emotion in emotion_ranges:
        min_chars_per_sec, max_chars_per_sec = emotion_ranges[selected_emotion]
        min_chars = int(video_duration * min_chars_per_sec)
        max_chars = int(video_duration * max_chars_per_sec)
        print(f"Emotion detected: {selected_emotion} - Range: {min_chars} to {max_chars} characters")
    else:
        # Default values if emotion is not found
        min_chars_per_sec, max_chars_per_sec = 6.0, 10.0  # More reasonable values
        min_chars = int(video_duration * min_chars_per_sec)
        max_chars = int(video_duration * max_chars_per_sec)
        print(f"Emotion not found in ranges: {selected_emotion} - Using default values: {min_chars} to {max_chars} characters")
    
    # Ensure ranges are reasonable
    min_chars = max(30, min_chars)  # Minimum 30 characters
    max_chars = max(min_chars + 50, max_chars)  # At least 50 characters more than minimum
    
    summary_prompt = (
        f"Role: You are an Audio Description Specialist for blind or visually impaired people.\n"
        f"Task: Generate a general description of the video based on the individual frame descriptions.\n\n"
        f"IMPORTANT - CHARACTER LIMIT RESTRICTION:\n"
        f"The video duration is {video_duration:.2f} seconds.\n"
        f"The complementary emotion detected is: {selected_emotion}\n"
        f"The main description MUST have between {min_chars} and {max_chars} characters in total.\n"
        f"DO NOT EXCEED THESE LIMITS UNDER ANY CIRCUMSTANCE.\n\n"
        f"Prosody analysis of the video:\n{json.dumps(prosody_content, ensure_ascii=False, indent=2)}\n\n"
        f"Style guidelines:\n"
        f"- Start directly with the description, without introductions\n"
        f"- Use direct and active language\n"
        f"- Avoid phrases like 'in the image', 'in the video', 'we can see', 'we observe', etc.\n"
        f"- Maintain a fluid and natural narrative tone\n"
        f"- Describe as if you were telling a story\n"
        f"- Use verbs in present tense and active voice\n"
        f"- Be concise but descriptive\n"
        f"- If a logo, symbol or identifying graphic element is identified in the frames, mention it and describe it in the general description as well\n\n"
        f"Response format:\n"
        f"1. First: The main description of the video (between {min_chars} and {max_chars} characters)\n"
        f"2. Second: A line saying 'ATTENTION MECHANISMS:' followed by the mechanisms used\n"
        f"3. Third: A line saying 'STATISTICS:' followed by:\n"
        f"   - Complementary emotion used: {selected_emotion}\n"
        f"   - Total number of characters in the main description: [number]\n"
        f"   - Characters per second: [number]\n"
        f"   - Allowed character range for that emotion: {min_chars} to {max_chars}\n\n"
        f"Descriptions of the video frames:\n{combined_text}"
    )    
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": "Generate the video description following the exact format specified."}
        ],
        max_tokens=1500
    )
    
    full_summary = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    
    # Separate different sections of the summary
    main_summary = ""
    attention_mechanisms = ""
    statistics_summary = ""
    
    # Search for different sections
    if "ATTENTION MECHANISMS:" in full_summary:
        parts = full_summary.split("ATTENTION MECHANISMS:")
        main_summary = parts[0].strip()
        remaining = "ATTENTION MECHANISMS:" + parts[1].strip()
        
        if "STATISTICS:" in remaining:
            stats_parts = remaining.split("STATISTICS:")
            attention_mechanisms = stats_parts[0].strip()
            statistics_summary = "STATISTICS:" + stats_parts[1].strip()
        else:
            attention_mechanisms = remaining
    else:
        main_summary = full_summary.strip()
    
    # Calculate character statistics
    if main_summary:
        # Clean up the main description from any additional text
        lines = main_summary.split('\n')
        description_lines = []
        for line in lines:
            line = line.strip()
            if line and not any(keyword in line.upper() for keyword in ["ATTENTION MECHANISMS:", "STATISTICS:", "SUMMARY:"]):
                description_lines.append(line)
            else:
                break
        
        # Join the description lines
        main_description_text = ' '.join(description_lines)
        char_count = len(main_description_text)
    else:
        char_count = 0
    
    chars_per_second = char_count / video_duration if video_duration > 0 else 0
    
    # Validate the summary
    if char_count == 0:
        print(f"❌ ERROR: The main description is empty")
    elif char_count > max_chars:
        print(f"⚠ WARNING: The number of characters in the description ({char_count}) exceeds the maximum allowed ({max_chars})")
    elif char_count < min_chars:
        print(f"⚠ WARNING: The number of characters in the description ({char_count}) is less than the minimum allowed ({min_chars})")
    else:
        print(f"✅ Description generated correctly: {char_count} characters (range: {min_chars}-{max_chars})")
    
    print(f"Tokens used in the summary: {tokens_used}")
    print(f"Total number of characters in the description: {char_count}")
    print(f"Characters per second: {chars_per_second:.2f}")
    print(f"Allowed range for {selected_emotion}: {min_chars} - {max_chars} characters")
    
    summary_json = {
        "main_summary": main_summary,
        "attention_mechanisms": attention_mechanisms,
        "statistics_summary": statistics_summary,
        "emotion": selected_emotion,
        "char_count": char_count,
        "chars_per_second": chars_per_second,
        "char_range": [min_chars, max_chars],
        "tokens_used": tokens_used
    }
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, ensure_ascii=False, indent=2)
    
    print("Video summary saved in", output_json)
    return summary_json

def analyze_prosody(api_key, image_folder, descriptions_json, video_duration, output_json="prosody_analysis.json"):
    openai.api_key = api_key
    
    with open(descriptions_json, "r", encoding="utf-8") as f:
        descriptions = json.load(f)
    
    # Use both description and attention mechanisms (as in v7)
    combined_text = " ".join([d["description"] + " " + d["attention_mechanisms"] for d in descriptions])
    
    # Request the IA to analyze the appropriate tone for the entire video
    tone_prompt = (
    f"Analyze the description to determine the prosodic modeling for an audio description \n"
    f"the video description, attention mechanisms and prosodic modeling: {combined_text}\n"
    f"Identify the main emotions detected (they must sum up to 100%). Then, provide a single general prosody for the entire video in the following format, based on the reference table:\n\n"
    f" Identify prosody for the image based on the following reference table:\n\n"
    	f"Reference prosodic modeling:\n\n"
    	f"- Main emotion: Joy\n"
    	f"  - Complementary emotion: Serenity\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: low, stable, no large variations\n"
   	f"  - Duration: Long, relaxed pauses\n"
    	f"  - Rhythm: Slow, regular, paused\n\n"
    	f"- Main emotion: Joy\n"
    	f"  - Complementary emotion: Ecstasy\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High, with wide variations\n"
    	f"  - Duration: Short, with exclamations\n"
    	f"  - Rhythm: Fast, energetic, dynamic\n\n"
    	f"- Main emotion: Trust\n"
    	f"  - Complementary emotion: Acceptance\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: Medium, warm, little variability\n"
    	f"  - Duration: Moderate\n"
    	f"  - Rhythm: Regular, fluid, no abrupt changes\n\n"
    	f"- Main emotion: Trust\n"
    	f"  - Complementary emotion: Admiration\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High, sometimes slightly ascending\n"
    	f"  - Duration: Moderate\n"
    	f"  - Rhythm: Emphatic, with certain emphasis, but not abrupt\n\n"
    	f"- Main emotion: Fear\n"
    	f"  - Complementary emotion: Apprehension\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: Slightly ascending, possible tremor or break\n"
    	f"  - Duration: Moderate, with shaky pauses\n"
    	f"  - Rhythm: Irregular, insecure, sometimes accelerated\n\n"
    	f"- Main emotion: Fear\n"
    	f"  - Complementary emotion: Terror\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High, with marked breaks\n"
    	f"  - Duration: Short, interrupted\n"
    	f"  - Rhythm: Very accelerated or abrupt, jade-like pauses\n\n"
    	f"- Main emotion: Surprise\n"
    	f"  - Complementary emotion: Distraction\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: Variable, sometimes erratic\n"
    	f"  - Duration: Variable (can be short or long)\n"
    	f"  - Rhythm: Inconsistent, with unexpected changes\n\n"
    	f"- Main emotion: Surprise\n"
    	f"  - Complementary emotion: Amazement\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High and ascending at the beginning, then variable\n"
    	f"  - Duration: Short or moderate, with brief pauses\n"
    	f"  - Rhythm: Brisk and irregular, marking surprise\n\n"
    	f"- Main emotion: Sadness\n"
    	f"  - Complementary emotion: Deep Thought\n"
    	f"  - Intensity: Low and subtle\n"
    	f"  - Tone: Medium-low, monotone or slightly descending\n"
    	f"  - Duration: Long, with reflective pauses\n"
    	f"  - Rhythm: Slow, reflective, almost meditative\n\n"
    	f"- Main emotion: Sadness\n"
    	f"  - Complementary emotion: Grief\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: Low, descending, monotone\n"
    	f"  - Duration: Long, with prolonged pauses\n"
    	f"  - Rhythm: Very slow, heavy, with marked silences\n\n"
    	f"- Main emotion: Disgust\n"
    	f"  - Complementary emotion: Boredom\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: Low, with little variability\n"
    	f"  - Duration: Long, sustained speech\n"
    	f"  - Rhythm: Slow, flat, no intensity changes\n\n"
    	f"- Main emotion: Disgust\n"
    	f"  - Complementary emotion: Aversion\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: Medium to high, dry or sharp\n"
    	f"  - Duration: Moderate, sometimes with abrupt pauses\n"
    	f"  - Rhythm: Sharp, aggressive, emphasizing rejection\n\n"
    	f"- Main emotion: Anger\n"
    	f"  - Complementary emotion: Annoyance\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: Medium, with small peaks of tension\n"
    	f"  - Duration: Moderate, shorter phrases\n"
    	f"  - Rhythm: A bit accelerated, interrupted, with breaks\n\n"
    	f"- Main emotion: Anger\n"
    	f"  - Complementary emotion: Fury\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High, aggressive, with abrupt changes\n"
    	f"  - Duration: Moderate or short, intercalated with exclamations\n"
    	f"  - Rhythm: Fast, explosive, with intense peaks\n\n"
    	f"- Main emotion: Anticipation\n"
    	f"  - Complementary emotion: Interest\n"
    	f"  - Intensity: Low\n"
    	f"  - Tone: High, slightly ascending\n"
    	f"  - Duration: Variable\n"
    	f"  - Rhythm: Fluid, agile, showing sustained attention\n\n"
    	f"- Main emotion: Anticipation\n"
    	f"  - Complementary emotion: Vigilance\n"
    	f"  - Intensity: High\n"
    	f"  - Tone: High, sometimes tense\n"
    	f"  - Duration: Moderate, with pauses to observe\n"
    	f"  - Rhythm: Agile, somewhat accelerated, attentive to changes\n"
f"Output format (for each main emotion):\n"
    f"Main emotion: [name] [percentage]%\n"
    f"Complementary emotion: [name]\n"
    f"Intensity: [text according to table]\n"
    f"Tone: [text according to table]\n"
    f"Duration: [text according to table]\n"
    f"Rhythm: [text according to table]\n\n"
    f"Example:\n"
    f"Main emotion: Joy 80%\n"
    f"Complementary emotion: Serenity\n"
    f"Intensity: Lowq\n"
    f"Tone: Medium-low, stable, no large variations\n"
    f"Duration: Long, relaxed pauses\n"
    f"Rhythm: Slow, regular, paused\n\n"
    f"No recommendations, additional interpretations, or suggested adjustments. Only respond following the format indicated for each detected main emotion.\n\n"
   )


    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": tone_prompt},
           {"role": "user", "content": "Give me a single general prosody for the entire video following the exact format specified"}
        ],
        max_tokens=3000
    )
    
    prosody_suggestion = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    print(f"Tokens used in prosody analysis: {tokens_used}")
    
    # Attempt to extract the main fields of the prosody
    prosody_json = {
        "main_emotion": None,
        "complementary_emotion": None,
        "intensity": None,
        "tone": None,
        "duration": None,
        "rhythm": None,
        "tokens_used": tokens_used
    }
    for line in prosody_suggestion.split('\n'):
        if line.lower().startswith("main emotion"):
            prosody_json["main_emotion"] = line.split(":")[1].strip()
        elif line.lower().startswith("complementary emotion"):
            prosody_json["complementary_emotion"] = line.split(":")[1].strip()
        elif line.lower().startswith("intensity"):
            prosody_json["intensity"] = line.split(":")[1].strip()
        elif line.lower().startswith("tone"):
            prosody_json["tone"] = line.split(":")[1].strip()
        elif line.lower().startswith("duration"):
            prosody_json["duration"] = line.split(":")[1].strip()
        elif line.lower().startswith("rhythm"):
            prosody_json["rhythm"] = line.split(":")[1].strip()
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(prosody_json, f, ensure_ascii=False, indent=2)
    print("Prosody analysis saved in:", output_json)
    return prosody_json

def process_video(video_path, output_base_folder="output_openia_ing", api_key=None):
    if api_key is None:
        print("API key is required for audio descriptions and prosody analysis")
        return
    
    # Create specific folder for this video
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_output_folder = os.path.join(output_base_folder, video_name)
    os.makedirs(video_output_folder, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"PROCESSING VIDEO: {video_name}")
    print(f"{'='*60}")
    
    keyframes_folder = os.path.join(video_output_folder, "keyframes")
    os.makedirs(keyframes_folder, exist_ok=True)
    
    keyframes, duration = extract_keyframes_clip_adjustable(
        video_path, 
        output_folder=keyframes_folder,
        diversity_threshold=0.2,  # Permissive for diversity
        similarity_threshold=0.3,  # Permissive for similarity
        min_keyframes=3,  # Reasonable minimum
        max_keyframes=30,  # Reasonable maximum
        frame_sampling_rate=15 # Sample every 15 frames
    )
    if not keyframes:
        print("Could not extract keyframes from the video")
        return
    
    print(f"\n{'='*50}")
    print(f"VIDEO INFORMATION:")
    print(f"Path: {video_path}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Format: {datetime.timedelta(seconds=int(duration))}")
    print(f"{'='*50}\n")
    print(f"Extracted {len(keyframes)} keyframes from the video")
    
    # Specific output files for this video
    audiodesc_json = os.path.join(video_output_folder, "audiodescriptions.json")
    prosody_json = os.path.join(video_output_folder, "prosody_analysis.json")
    summary_json = os.path.join(video_output_folder, "video_summary.json")
    
    # Process descriptions
    print(f"\nGenerating audio descriptions for {video_name}...")
    descriptions = generate_audiodescriptions(api_key, keyframes_folder, output_json=audiodesc_json, video_duration=duration)
    
    # Analyze prosody
    print(f"\nAnalyzing prosody for {video_name}...")
    prosody_suggestion = analyze_prosody(api_key, keyframes_folder, audiodesc_json, duration, output_json=prosody_json)
    
    # Generate summary with verification and retries
    print(f"\nGenerating summary for {video_name}...")
    max_retries = 3
    retry_count = 0
    video_summary = None
    
    while retry_count < max_retries:
        try:
            video_summary = summarize_audiodescriptions(api_key, audiodesc_json, duration, prosody_json, output_json=summary_json)
            
            # Verify if the summary is valid
            if video_summary and "main_summary" in video_summary:
                main_summary = video_summary["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ Summary generated successfully and validated")
                    break
                else:
                    print(f"⚠ Invalid summary detected: '{main_summary[:50]}...'")
                    print(f"Retrying summary generation (attempt {retry_count + 2}/{max_retries})...")
            else:
                print(f"⚠ Summary is empty or missing main_summary, retrying...")
                
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            print(f"Retrying... (attempt {retry_count + 2}/{max_retries})")
        
        retry_count += 1
        if retry_count < max_retries:
            print("Waiting 5 seconds before retrying...")
            time.sleep(5)
    
    if retry_count >= max_retries:
        print(f"❌ Could not generate a valid summary after {max_retries} attempts")
        if video_summary and "main_summary" in video_summary:
            print(f"Last summary generated: '{video_summary['main_summary'][:100]}...'")
    else:
        print(f"✅ Final valid summary generated in {retry_count + 1} attempts")
    
    print(f"\n{'='*50}")
    print(f"PROCESS COMPLETED FOR: {video_name}")
    print(f"{'='*50}")
    print(f"Generated in {video_output_folder}:")
    print(f"1. Keyframes in {keyframes_folder}")
    print(f"2. Descriptions in {audiodesc_json}")
    print(f"3. Video summary in {summary_json}")
    print(f"4. Prosody analysis in {prosody_json}")
    print(f"{'='*50}\n")
    
    return video_output_folder

def reprocess_summary_only(video_name, output_base_folder="output_openia_ing", api_key=None, max_retries=3):
    """
    Reprocesa solo el resumen de un video específico, reutilizando las audiodescripciones ya generadas
    """
    if api_key is None:
        print("API key is required to reprocess the summary")
        return False
    
    video_output_folder = os.path.join(output_base_folder, video_name)
    
    # Verify that required files exist
    audiodesc_json = os.path.join(video_output_folder, "audiodescriptions.json")
    prosody_json = os.path.join(video_output_folder, "prosody_analysis.json")
    summary_json = os.path.join(video_output_folder, "video_summary.json")
    
    if not os.path.exists(audiodesc_json):
        print(f"❌ Audio descriptions file not found: {audiodesc_json}")
        return False
    
    if not os.path.exists(prosody_json):
        print(f"❌ Prosody analysis file not found: {prosody_json}")
        return False
    
    print(f"\n{'='*60}")
    print(f"REPROCESSING ONLY THE SUMMARY FOR: {video_name}")
    print(f"{'='*60}")
    
    # Read duration from existing audio descriptions
    try:
        with open(audiodesc_json, "r", encoding="utf-8") as f:
            descriptions = json.load(f)
        
        # Calculate approximate duration based on number of keyframes
        # Assuming each keyframe represents approximately 1 second
        duration = len(descriptions) * 1.0  # Simple approximation
        
        print(f"Estimated video duration: {duration:.2f} seconds")
        
    except Exception as e:
        print(f"Error reading audio descriptions: {str(e)}")
        return False
    
    # Reprocess the summary with verification
    retry_count = 0
    video_summary = None
    
    while retry_count < max_retries:
        try:
            print(f"\nGenerating summary (attempt {retry_count + 1}/{max_retries})...")
            video_summary = summarize_audiodescriptions(api_key, audiodesc_json, duration, prosody_json, output_json=summary_json)
            
            # Verify if the summary is valid
            if video_summary and "main_summary" in video_summary:
                main_summary = video_summary["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ Summary regenerated successfully and validated")
                    print(f"Summary: '{main_summary[:100]}...'")
                    return True
                else:
                    print(f"⚠ Invalid summary detected: '{main_summary[:50]}...'")
                    if retry_count < max_retries - 1:
                        print(f"Retrying summary generation...")
            else:
                print(f"⚠ Summary is empty or missing main_summary, retrying...")
                
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            if retry_count < max_retries - 1:
                print(f"Retrying...")
        
        retry_count += 1
        if retry_count < max_retries:
            print("Waiting 5 seconds before retrying...")
            time.sleep(5)
    
    print(f"❌ Could not generate a valid summary after {max_retries} attempts")
    if video_summary and "main_summary" in video_summary:
        print(f"Last summary generated: '{video_summary['main_summary'][:100]}...'")
    
    return False

def check_and_reprocess_invalid_summaries(output_base_folder="output_openia_ing", api_key=None, max_retries=3):
    """
    Verifica todos los resúmenes en la carpeta de salida y reprocesa los que son inválidos
    """
    if api_key is None:
        print("API key is required to reprocess summaries")
        return
    
    if not os.path.exists(output_base_folder):
        print(f"❌ Folder {output_base_folder} does not exist")
        return
    
    print(f"\n{'='*60}")
    print(f"CHECKING AND REPROCESSING INVALID SUMMARIES")
    print(f"Folder: {output_base_folder}")
    print(f"{'='*60}")
    
    # Get all video folders
    video_folders = []
    for item in os.listdir(output_base_folder):
        item_path = os.path.join(output_base_folder, item)
        if os.path.isdir(item_path):
            video_folders.append(item)
    
    if not video_folders:
        print("No video folders found to check")
        return
    
    print(f"Found {len(video_folders)} video folders to check")
    
    valid_summaries = []
    invalid_summaries = []
    reprocessed_summaries = []
    
    for video_folder in video_folders:
        summary_json = os.path.join(output_base_folder, video_folder, "video_summary.json")
        
        if not os.path.exists(summary_json):
            print(f"⚠ {video_folder}: Summary file not found")
            invalid_summaries.append(video_folder)
            continue
        
        try:
            with open(summary_json, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            
            if "main_summary" in summary_data:
                main_summary = summary_data["main_summary"]
                if is_valid_summary(main_summary):
                    print(f"✓ {video_folder}: Valid summary")
                    valid_summaries.append(video_folder)
                else:
                    print(f"❌ {video_folder}: Invalid summary - '{main_summary[:50]}...'")
                    invalid_summaries.append(video_folder)
                    
                    # Attempt to reprocess
                    print(f"🔄 Reprocessing summary for {video_folder}...")
                    if reprocess_summary_only(video_folder, output_base_folder, api_key, max_retries):
                        reprocessed_summaries.append(video_folder)
                        print(f"✅ {video_folder}: Summary reprocessed successfully")
                    else:
                        print(f"❌ {video_folder}: Could not reprocess the summary")
            else:
                print(f"❌ {video_folder}: Summary missing main_summary")
                invalid_summaries.append(video_folder)
                
        except Exception as e:
            print(f"❌ {video_folder}: Error reading summary - {str(e)}")
            invalid_summaries.append(video_folder)
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"SUMMARY OF VERIFICATION AND REPROCESSING")
    print(f"{'='*60}")
    print(f"Valid summaries: {len(valid_summaries)}")
    print(f"Invalid summaries: {len(invalid_summaries)}")
    print(f"Successfully reprocessed summaries: {len(reprocessed_summaries)}")
    
    if valid_summaries:
        print(f"\nValid summaries:")
        for folder in valid_summaries:
            print(f"  ✓ {folder}")
    
    if invalid_summaries:
        print(f"\nInvalid summaries:")
        for folder in invalid_summaries:
            print(f"  ❌ {folder}")
    
    if reprocessed_summaries:
        print(f"\nSuccessfully reprocessed summaries:")
        for folder in reprocessed_summaries:
            print(f"  ✅ {folder}")
    
    print(f"{'='*60}")

def process_all_videos(segmentos_folder="segmentos", output_base_folder="output_openia_ing", api_key=None):
    """
    Procesa todos los videos en la carpeta segmentos de manera individual
    """
    if not os.path.exists(segmentos_folder):
        print(f"Error: Folder {segmentos_folder} does not exist")
        return
    
    # Get all video files
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
    video_files = []
    
    for filename in os.listdir(segmentos_folder):
        if any(filename.lower().endswith(ext) for ext in video_extensions):
            video_path = os.path.join(segmentos_folder, filename)
            video_files.append(video_path)
    
    if not video_files:
        print(f"No video files found in {segmentos_folder}")
        return
    
    # Sort files by name
    video_files.sort()
    
    print(f"Found {len(video_files)} videos to process:")
    for video_path in video_files:
        print(f"  - {os.path.basename(video_path)}")
    
    print(f"\n{'='*60}")
    print("STARTING PROCESSING OF ALL VIDEOS")
    print(f"{'='*60}")
    
    processed_videos = []
    failed_videos = []
    
    for i, video_path in enumerate(video_files, 1):
        try:
            print(f"\nProcessing video {i}/{len(video_files)}: {os.path.basename(video_path)}")
            output_folder = process_video(video_path, output_base_folder, api_key)
            if output_folder:
                processed_videos.append((video_path, output_folder))
        except Exception as e:
            print(f"Error processing {os.path.basename(video_path)}: {str(e)}")
            failed_videos.append(video_path)
    
    # Final summary
    print(f"\n{'='*60}")
    print("FINAL PROCESSING SUMMARY")
    print(f"{'='*60}")
    print(f"Successfully processed videos: {len(processed_videos)}")
    print(f"Videos with errors: {len(failed_videos)}")
    
    if processed_videos:
        print(f"\nSuccessfully processed videos:")
        for video_path, output_folder in processed_videos:
            print(f"  ✓ {os.path.basename(video_path)} → {output_folder}")
    
    if failed_videos:
        print(f"\nVideos with errors:")
        for video_path in failed_videos:
            print(f"  ✗ {os.path.basename(video_path)}")
    
    print(f"\nAll output files can be found in the folder: {output_base_folder}")
    print(f"{'='*60}")

if __name__ == "__main__":
    api_key = "YOUR_API_KEY"
    
    # Processing options
    import sys
    
    if len(sys.argv) > 1:
        option = sys.argv[1].lower()
        
        if option == "reprocess_summary":
            # Reprocess only the summary of a specific video
            if len(sys.argv) > 2:
                video_name = sys.argv[2]
                reprocess_summary_only(video_name, "output2", api_key)
            else:
                print("Usage: python Descripciones.py reprocess_summary <video_name>")
        
        elif option == "check_summaries":
            # Check and reprocess all invalid summaries
            output_folder = sys.argv[2] if len(sys.argv) > 2 else "output2"
            check_and_reprocess_invalid_summaries(output_folder, api_key)
        
        elif option == "process_all":
            # Process all videos (original behavior)
            segmentos_folder = sys.argv[2] if len(sys.argv) > 2 else "PruebaIAS"
            output_folder = sys.argv[3] if len(sys.argv) > 3 else "output_openia_ing"
            process_all_videos(segmentos_folder=segmentos_folder, output_base_folder=output_folder, api_key=api_key)
        
        else:
            print("Available options:")
            print("  python Descripciones.py process_all [segmentos_folder] [output_folder]")
            print("  python Descripciones.py reprocess_summary <video_name>")
            print("  python Descripciones.py check_summaries [output_folder]")
    else:
        # Default behavior: process all videos
        process_all_videos(segmentos_folder="PruebaIAS", output_base_folder="output_openia_ing", api_key=api_key)
    
