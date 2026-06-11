import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig


def call_gemini(project_id, location, prompt):
    vertexai.init(project=project_id, location=location)

    model = GenerativeModel("gemini-1.5-flash-002")

    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )

    return response.text.strip()
