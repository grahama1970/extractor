 has typer been removed from all steps; /home/graham/
  workspace/experiments/extractor/src/extractor/
  pipeline/steps
  does each step easy to use main block that can be run
  with an expected input and putput that can be easily
  debugged in the VSCode debugger. The original test
  pdf is: /home/graham/workspace/experiments/extractor/
  data/input/pipeline/
  BHT_CV32A65X_with_requirements_noannots.pdf

ask copilot in the chat for a comprehensive review of th entire pipeline focusing on missing functionality, aspiration/brittle features, unnecesary adhoc/bespoke functions, strengths, the ability to handle a wide variety of pdf. Proved file paths and a list of clarifying questions and ask for unified diff as a file artifact and answer to your qeustins
template:


 in the devops project, we have been having good collaborative results
  by the devops agent dynaically creating a notebook viewer, how might
  we do that here for the extractor project? /home/graham/workspace/
  experiments/devops/notebooks/sparta_rationales_plan.ipynb


curl -X POST \
		https://llm.chutes.ai/v1/chat/completions \
		-H "Authorization: Bearer $CHUTES_API_KEY" \
	-H "Content-Type: application/json" \
	-d '  {
    "model": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "messages": [
      {
        "role": "user",
        "content": "Tell me a 250 word story."
      }
    ],
    "stream": true,
    "max_tokens": 1024,
    "temperature": 0.7
  }'