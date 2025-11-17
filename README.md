### the intvrface for the model to interact with the world

this is the wrapper around an AI model whether that is the powerful primy model that starts the utopia bootstrap or just a normal general model like claudy   
the model needs a software layer to interact with the computer for both capability and safety monitoring  


### intvrface allows the model to

call programs via MCP (all following tools should be wrapped in MCP)  
control a computer via terminal  
control a computer via GUI  
use anthropic agent sdk: file edit tools  
UI for humans to monitor and manage multi agent progress  
voice chat to speak with humans  
custom MCPs (todo, svmbolcore, phvsicsim)


### memory functionality

(some additional functionality for frozen weights token discretized transformers which i imagine primy won't be and won't need but claudy for now does)


better context management with auto summarization  
note editing tools for long term continual learning  
MCTS creative solution exploration

description of implementation of context management:  

original_context.jsonl: all model outputs and environment data goes here  

streaming_context.jsonl: what the model reads from. everything added to original context also added here.  

summarized_context.jsonl: once the token count that goes from the beginning of streaming_context.jsonl to the last five messages from the end reaches like 40k, a specialized prompt gets auto triggered and the model will summarize the 40k context into something like < 2k words. the summary goes into summarized.jsonl. and the streaming_context jsonl becomes that summarized context plus the last five messages.   

note that original_context.jsonl and summarized_context.jsonl are only for logging and monitoring purposes and the model always only reads from streaming_context.jsonl.   

description of implementation of note taking:  
this is basically a file edit but just prompted to allow the model to take long term notes in different .md files. and also read them, reading them just adds them to the context like other outputs from function calls.  

description of implementation of MCTS:  
to be determined


### tech stack:
the goal is maximal simplicity and transparency.  
frontend we are using pure html css js.   
for backend we are using python and fastapi  
for database we are using jsonl  
for agent launching later we are using docker.  
we should use anthropic agent sdk as much as possible and avoid rewriting things  


### design:
we are using the infinite scroll zoom board design. with components being horizontal rectangles. with the techno paradisal theme in base.css.   
background and component is gray themed, with text and border being a pastel / neon color. different colors symbolize different states.  

in the agent page: 
not working: gray.  
learning (reading files, searching files, web searching, GUI seeing results): purple  
thinking (reasoning): blue  
acting (coding, executing files): orange  
done: black  
subtasks are organized left to right according to dependency


### future functionality

model wrapper rather than just claude api

a special permanent conversational claudy that is undeletable and just better tuned to talk with the user and take notes on user information. no computer control or MCP for this one.  

a project page. each project is a folder that is clickable that goes to another page. each project page can contain MULTIPLE agents. this follows a sort of to do app graph of parallel tasks and serial tasks. different agents can work on the parallel tasks at the same time.  

maybe mech interp visualization?

although maybe later i can do more functionality that allow the model to go back and read original context or for the streaming context to be like the last 5 summarized contexts plus some original context and only prompt the model to summarize original context (don't summarize summaries).     
