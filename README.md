### the intvrface for the model to interact with the world

### intvrface allows claudy to:  

control a computer via terminal  
control a computer via GUI  
use anthropic agent sdk: file edit tools  
use MCP: custom tools. i.e. my other projects like svmbolsolve and phvsicsim over api.  

manage context better and hold long term memory in jsonl with auto context summarization and note editing    
streaming context made up of original tokens, summarized tokens, permanent tokens   
display streaming context  

plan tasks (user controlled)  
launch parallel agents for parallel tasks  

UI to monitor agent progress

interact with user through voice chat  


### features:

#### common claudy

this is a claudy context that is like a normal chat webpage. it never gets deleted and it has voice chat.  
this claudy should know EVERYTHING about the user over time and also all the project descriptions.  

auto context summary feature: 
original_tokens: jsonl made up of the latest model output / inputs from documents, web searches, terminal results
summarized_tokens: once original tokens reaches 20k, prompt model to summarize it into around 1k tokens. 
streaming_tokens: what the model actually sees. made up of like 10 past summarized_token chunks and the latest original tokens
permanent_tokens: say there are 10 summarized token slots. there would be one permanent token slot that is a .md file not a jsonl that the outdated summarized tokens gets prompted to write crucial information into. this would be project.md or some user description .md like interests.md or relationship.md. for common_claudy it will have to write to all different project.md files and also the user .md files. for agent claudies maybe they only have a like a specific task.md to read and write to.  
the streaming tokens should be visible when clicked so i can see the same things the model sees and when i click something. overall streaming tokens format is:  
prompt  
permanent tokens (all of it)  
summarized tokens (latest 5 paragraphs) 
original tokens (latest < 20k tokens )  

these for common claudy will be stored in data/commom  

maybe i will later add an mcp that draws connection between the actual original thoughts and tokens with the summarized and allow the model to inspect original but not now.  

for the common claudy only as opposed to the agent claudy generates like "user basic information", "project svmbolsolve", "project mindology", "user end goals and motivations" etc. and store them in the data/core_memory.jsonl file. this further a summarized version of the previously summarized context. many things could be omitted like trivial questions or whatever.   

you should be able to something to see exactly what context claudy is reading from. 
the dark green chat button should exist in all three pages

#### projects and tasks (page 2)

basically a to do app of different projects. these are all parallel relationship but you can click and drag then to sort of indicate a relationship. like mindology, svmbolsolve, different specific coding projects, etc. all projects. projects are folders on the local computer. they are mostly coding projects but could also be research projects with a lot of .md files. it must have a git. 

each projects when double clicked goes to the next page. 


#### agents (page 3)

each project has tasks. tasks can also have tasks. this can be a parallel relationship or a serial relationship. defined through a direct acylic tree defined through an adjacency list and stored as json in data/common/tvdo.json  
each agent is a claudy instance and context associated with a task. one to one relationship. if task is complex and parallel break it into subtasks and launch an agent for each  
each agent has a folder named data/project/task_name. the original context and auto summarized contexts are stored as jsonl in this folder.  
each agent also has a user chat interrupt system if the user intervenes. but mostly it should be autonomous  
maybe i will implement common claudy intervening later as a reviewer but for now agent should self review  
each agent should have a docker for computer use. the computer use features are said before in the "intvrface allows claudy to" section. each agent should have a git branch it works on and clear goals so it doesn't mess up other files it's not supposed to touch  
each task agent should be visible like i should be able to click the task and it expands and i see exactly what it is doing. including a split screen like a terminal/GUI and a thought page of current token outpus with context on top. note that context could change i want to see the context it is reading from not just all the past tokens.   
maybe later i give a sub tvdo chart MCP to the model just for it to plan better? one that is only for it to use.  
each coding agent importantly must have a self enforced testing loop where it runs the code and writes the tests and sees the code pass the test or if it's frontend see the code looks right in the GUI and then stop only when everything looks ok.  
maybe later i ask common claudy to work as a reviewer approval but for now the user will review things and give feedback  
you should be able to click an agent and see exactly what context it is drawing from, and it's current computer screen (terminal or GUI)

maybe later i do a um seperate folder enviroment and a complete autonomy mode where common_claudy does not talk to me but just does what ITSELF wants to do and make it's own projects.  



### tech stack:
the goal is maximal simplicity and transparency.  
frontend we are using pure html css js.   
for backend we are using python and fastapi  
for databse we are using jsonl  
for agent launching later we are using docker.  
we should use anthropic agent sdk as much as possible and avoid rewriting things  


### design:
we are using the infinite scroll zoom board design. with components being horizontal rectangles. with the techno paradisal theme in base.css.   
background and component is gray themed, with text and border being a pastel / neon color. different colors symbolize different states.  

in the projects page:  
bottom right: "chat"  : dark green (dark green for common context never deleted)  
tasks: light terminal neon green (light green for specific agent context deleted after sub task complete)

in the agent page: 
not started: gray.  
learning (reading files, searching files, web searching, GUI seeing results): purple  
thinking (reasoning): blue  
acting (coding, executing files): orange  
done: black  
subtasks are organized left to right according to dependency


# gradual to do:
this will be built version by version. each time with more features / better design. 

# version 1

chat page UI. anthropic api chat. common_claudy prompt. auto context gen. the 4 context divide. original_tokens.jsonl, summarized_tokens.jsonl, permanent_tokens.jsonl, and streaming_tokens.jsonl, each with their own prompts. ok make it so only the PROMPT for common claudy and agent claudy is different. so the prompt of common claudy asks for it to remeber in permanent memory the um user facts and all project facts and for agent claudy it only ask it to remember important coding project specific facts and um like web search result for new repos or something. the important thing is i should see to be DRY and use the same structure for different things. also the tvdo should be the same structure for each project to task relationship but also for each individual agent. maybe permanent memory is in .MD format not jsonl? and note that the project.MD for each project is shared between common claudy and agent claudy.   
yeah basically the first page UI and backend.  
chat with common claudy, 4 context jsonls in data, projects and projects mds


# version 2
add voice chat. make sure it is LOCAL not over api. voice chat with common claudy.  
add the tvdo tasks. and their seperate claudies, page 2.   

# version 3
terminal control. file edits. git branches each agent has one
