import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from src.kb_generator import DemoKnowledgeBaseGenerator

def main():
    parser = argparse.ArgumentParser(description="ImpactAgent: CS2 Replay (.dem) to LLM Knowledge Base (.md) Generator")
    parser.add_argument("--demo", type=str, default="scripts/demos/trashgame.dem", help="Path to CS2 .dem replay file")
    parser.add_argument("--output", type=str, default="", help="Path to output Markdown Knowledge Base (.md) file")
    args = parser.parse_args()

    print("==========================================================================")
    print(" 🚀 IMPACTAGENT: CS2 REPLAY TO LLM KNOWLEDGE BASE GENERATOR (demoparser2)")
    print("==========================================================================")

    demo_path = args.demo
    if not os.path.exists(demo_path):
        alt = os.path.join("scripts", "demos", os.path.basename(demo_path))
        if os.path.exists(alt):
            demo_path = alt

    if not os.path.exists(demo_path):
        print(f"Error: Demo file not found at '{args.demo}'")
        sys.exit(1)

    # Determine Output Knowledge Base Path
    output_path = args.output
    if not output_path:
        filename = os.path.splitext(os.path.basename(demo_path))[0]
        output_path = os.path.join("data", f"{filename}_kb.md")

    print(f"Parsing demo replay file via demoparser2: [{demo_path}] ...")
    generator = DemoKnowledgeBaseGenerator(demo_path)
    generated_file = generator.generate_markdown_kb(output_path)

    print("\n--------------------------------------------------------------------------")
    print(f"✅ SUCCESS! Created Knowledge Base (.md) file for LLM:")
    print(f"   📄 File Path: {os.path.abspath(generated_file)}")
    print("--------------------------------------------------------------------------\n")

if __name__ == "__main__":
    main()
