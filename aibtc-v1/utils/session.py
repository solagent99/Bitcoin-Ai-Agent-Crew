import anthropic
import inspect
import importlib
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from typing import Optional
from crewai import Agent, LLM

from utils.crews import AIBTC_Crew


def load_env_vars():
    load_dotenv()
    env_vars = {}
    for key, value in os.environ.items():
        env_vars[key] = value
    return env_vars


def init_session_state():
    env_vars = load_env_vars()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "agents" not in st.session_state:
        st.session_state.agents = {}

    if "tasks" not in st.session_state:
        st.session_state.tasks = {}

    if "tasks_search_term" not in st.session_state:
        st.session_state.tasks_search_term = ""

    # Initialize other session state variables
    defaults = {
        "api_key": env_vars.get("OPENAI_API_KEY", ""),
        "api_base": env_vars.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
        "model": env_vars.get("OPENAI_MODEL_NAME", "gpt-4o-mini"),
        "embedder_provider": env_vars.get("OPENAI_EMBEDDER_PROVIDER", "openai"),
        "embedder_model": env_vars.get(
            "OPENAI_EMBEDDER_MODEL", "text-embedding-3-small"
        ),
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Initialize the LLMs
    if "llm" not in st.session_state:
        st.session_state.llm = LLM(
            model=st.session_state.model,
            api_key=st.session_state.api_key,
            base_url=st.session_state.api_base,
        )
        st.session_state.embedder = {
            "provider": st.session_state.embedder_provider,
            "config": {"model": st.session_state.embedder_model},
        }

    if "crew_mapping" not in st.session_state:
        st.session_state.crew_mapping = generate_crew_mapping()


def update_session_state(key, value):
    st.session_state[key] = value


def generate_crew_mapping():
    crew_mapping = {}

    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    crews_dir = os.path.join(current_dir, "..", "crews")

    if not os.path.exists(crews_dir):
        raise FileNotFoundError(f"The crews directory does not exist: {crews_dir}")

    crew_files = [
        f for f in os.listdir(crews_dir) if f.endswith(".py") and not f.startswith("__")
    ]

    for filename in crew_files:
        module_name = f"crews.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)

            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AIBTC_Crew)
                    and obj != AIBTC_Crew
                ):
                    # Create an instance to get the name
                    try:
                        instance = obj(st.session_state.embedder)
                        crew_name = instance.name
                        crew_description = instance.description
                    except Exception as e:
                        print(f"Error creating instance of {name}: {e}")
                        crew_name = name.replace("Crew", "").replace("_", " ")

                    crew_mapping[crew_name] = {
                        "description": crew_description,
                        "class": obj,
                        "task_inputs": getattr(obj, "get_task_inputs", lambda: []),
                    }
        except ImportError as e:
            print(f"Error importing {module_name}: {e}")

    return crew_mapping


def get_crew_class(crew_name: str) -> Optional[type]:
    crew_info = st.session_state.crew_mapping.get(crew_name)
    return crew_info["class"] if crew_info else None


def get_crew_inputs(crew_name: str):
    crew_info = st.session_state.crew_mapping.get(crew_name)
    if crew_info and "task_inputs" in crew_info:
        return crew_info["task_inputs"]()
    return []
