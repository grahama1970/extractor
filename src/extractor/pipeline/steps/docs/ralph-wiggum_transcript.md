I'm going to do something I don't 
 usually do for these videos and give it 
 a pretty hypy intro. One of the dreams 
 of coding agents is that you can wake up 
 in the morning to working code that your 
 coding agent has worked through your 
 backlog and has just spit out a whole 
 bunch of code for you to review and it 
 works. Now, people have been trying to 
 make this work for a while with agent 
 swarms and meshes and orchestrators. But 
 what if I told you that the way to get 
 this to work is with a for loop. I'm 
 going to show you a technique for 
 running coding agents that makes it 
 devilishly simple that is a vast 
 improvement over any other AI coding 
 orchestration setup I've ever tried and 
 allows you to actually ship working 
 stuff with longrunning coding agents and 
 everyone's calling it Ralph Wigum. This 
 is credited to Jeffrey Huntley and even 
 though this came out in 14th of July, 
 Ralph is kind of having a moment right 
 now. That's because this article 
 advocates an extremely simple approach 
 to agent orchestration and it requires 
 the underlying coding model to be really 
 really good and with Opus 4.5 and GPT 
 5.2 that have come out they are very 
 very good and it means that simpler 
 approaches like this are now really 
 viable and I think to be recommended. So 
 let's get started and understand why 
 Ralph is so good. Before we get stuck 
 into code I want to talk about what 
 software engineers actually do. I'm 
 going to use some terms from agile, not 
 because I really care about agile, but 
 most software developers out there will 
 be working in some form of agile 
 terminology. You usually have as a 
 software engineer a sprint of things 
 that you need to get done. Each of these 
 are little tasks that need to be grabbed 
 by the engineers and done before the end 
 of the sprint. A sprint is usually time 
 boxed, right? So, you start it on some 
 date and it ends. Let's say you can have 
 one week sprints, two week sprints, 
 whatever. But in the AI coding world, 
 you don't need to worry about time 
 boxing these sprints because the AI has 
 infinite amounts of endurance and can 
 work forever in theory. And so in AI 
 coding, this is really just a list of 
 tasks that needs to be done in some 
 order or another. So how would you get 
 an AI to work through this entire 
 backlog? Well, what you could do is you 
 could get 16 AI agents to individually 
 work on each task, but that would be 
 absolutely hellish because you'd end up 
 with a ton of merge conflicts and tasks 
 might have like little dependencies 
 between each one that it's quite hard to 
 spot by just looking at it. One thing 
 you obviously couldn't do is get a 
 single AI to work through each one 
 because probably these tasks are too big 
 all collectively to fit in a single 
 context window. So, the AI would get 
 confused, it would break, and you'd end 
 up with crappy code. I've got a video on 
 context windows if you want to 
 understand more about what I mean. And 
 so what most smart AI coders are doing 
 now is they would split this into a 
 multi-phase plan. An LLM would then be 
 able to work through each one of these 
 clearing its context as it went. You 
 could imagine this multihase plan was 
 actually a markdown file where it 
 explains each step that it needs to be 
 done. And you would create this markdown 
 file with an LLM as well. So you go into 
 plan mode in clawed code or something 
 and you would create this big plan that 
 the LLM would then in multiple context 
 windows go and progress through. This is 
 previously before I discovered Ralph how 
 I've been doing my AI coding. I make 
 these big plans and then I say okay do 
 phase one then do phase two then do 
 phase three. But one thing I've noticed 
 here is it's really hard to add stuff to 
 the plan. When you need to add a new 
 item here, then you somehow got to kind 
 of squeeze it between two different 
 things here. You as the kind of 
 orchestrator need to like the human 
 orchestrator need to work out where it 
 fits in the exact place in the multihase 
 plan. And of course, you need to figure 
 out all of these arrows here. You need 
 to figure out the exact right path to go 
 through. And of course, the LLM can help 
 you, but it's still a lot of work that 
 you need to do up front. And the thing 
 that always bothered me is that this 
 doesn't really reflect how engineers 
 actually work. Real engineers will take 
 a look at a canon board and they will 
 go, "Okay, I need to work on this task 
 next." Then they will take that task and 
 complete it, go back to the board and 
 notice, okay, that task is missing. Let 
 me find the next highest priority task. 
 Then they complete that and the cycle 
 continues until the sprint is complete. 
 This means that when you're designing 
 the sprint, all you're doing is 
 designing how it should look at the very 
 end. And so if you need to add a task 
 into this loop, all you do is just add a 
 new thing in there. You add an extra 
 specification for what the feature 
 should look like at the end. Now if we 
 look closely here, we have got ourselves 
 a loop where you specify some list of 
 tasks to complete. The LLM goes and 
 completes that task and then when all of 
 the tasks have disappeared and there's 
 nothing left for it, it then completes 
 the loop and it's done. To go back to 
 Jeffrey Hunt's article, this is what 
 Ralph is. Ralph is a bash loop. You give 
 the LLM some task to complete or list of 
 tasks and you run it again and again and 
 again until it's complete. Now, at this 
 point, you probably have a bunch of 
 questions about this approach. So, let's 
 dive into code to answer them. We are 
 inside a very important repo to me, 
 which is my course video manager. This 
 is an app that I built that I use to 
 edit my videos, to manage my courses, to 
 use AI to help me write articles. It's a 
 complex piece of code. And inside the 
 plans directory here, I have a Ralph.sh 
 file. Let's explain this line by line. 
 First of all, we set the error mode to 
 make sure that any errors in here are 
 thrown. The way you run this loop is you 
 run it with ralph.sh and you pass in the 
 maximum number of iterations you want it 
 to go through the loop. For instance, if 
 I open up a terminal here and I just run 
 plans ralph.sh, then it's going to yell 
 at me for not passing in the max number 
 of iterations. We then run a for loop 
 where we stop the for loop if we pass 
 the max number of iterations. In other 
 words, yeah, we're running this for 
 loop, but we do want a stop condition in 
 in case the LLM decides never to 
 complete. We then do a bit of logging. 
 We log out a line. And then we run 
 clawed code. It doesn't really matter 
 which one you run here, whether you're 
 running clawed, whether you're running 
 open code, whether you're running 
 codeex, as long as it's some kind of LLM 
 that you can or coding agent that you 
 can invoke via the CLI. We then pass it 
 two really important local files on the 
 file system. First of all, we pass it a 
 plans prd.json. Let's open that up to 
 see what that looks like here. This is a 
 JSON file with a bunch of different user 
 stories in it. For instance, I've been 
 working on a feature in my video editor 
 called beats where I can just specify a 
 clip to add a slight bit of a gap at the 
 end of it. In the UI, beats should 
 display as three orange ellipses dots 
 below the clip. So, you add a beat to a 
 clip. Verify that three orange dots 
 appear below the clip. Verify they're 
 orange colored. Verify they form an 
 ellipses pattern. As you can probably 
 tell, I've been iterating on this file 
 with an LLM to help me. Each one of 
 these items in this PRD product 
 requirements document has a passes flag 
 on it. This tells the LLM whether this 
 is actually passing or not in the 
 application code. And so this forms not 
 only a product requirements document, 
 but a to-do list. We can see that the 
 pre-recording checklist or let's go to 
 the one above. Delete video shows 
 confirmation dialogue before deleting. 
 We can see that that is passing in the 
 UI right now. In other words, this work 
 is complete and we don't need to do 
 anymore. So, as you can tell, this PRD 
 represents this list of tasks here. Each 
 one of these tasks represents a single 
 item in that array and we can consider 
 it passing when it's got that passes 
 true on it. Another important file that 
 we're passing in immediately is 
 progress.txt. 
 This file here is a free text log that 
 the LLM can append to with its learnings 
 as you went through. We can think of 
 this as the things that it learned on 
 this sprint. again implementing a bunch 
 of PRD items here. And so this 
 represents the LLM's memory for this 
 sprint. When we get to the end of the 
 sprint, I would usually just delete 
 this, but this as well as the PRD is 
 what the LLM sees going into its loop. 
 In the prompt, we give the LLM a list of 
 steps to complete. We say find the 
 highest priority feature to work on and 
 work only on that feature. I noticed 
 that it was often just choosing the 
 first one in the list. So I said, this 
 should be the one that you decide has 
 the high priority, not necessarily the 
 first in the list. I'll get to number 
 two in a minute, but number three says 
 update the PRD with the work that was 
 done. What it usually does at this point 
 is it just marks the right PRD items as 
 passes true and then append your 
 progress to the progress.txt file. 
 Append is really important. If you tell 
 it to update, it will usually just 
 update the entire file, whereas append 
 means it usually just goes and sticks 
 some stuff at the end. Just got some 
 loose advice here saying use this to 
 leave a note for the next person working 
 in your codebase. I then say make a git 
 commit of that feature. So it commits 
 the PRD, commits the progress.txt file, 
 and then it commits all the work that 
 it's done. So each time we're going 
 through a loop here, we're getting a git 
 commit. This is really, really useful 
 because it means that the LLM can query 
 the git history as well as see the 
 progress.txt to see what's been done 
 previously and to give it context for 
 what it needs to do now. And finally, we 
 say only work on a single feature. The 
 reason we say this and the reason we do 
 this whole PRD dance at all is to 
 prevent the LLM from biting off more 
 than it can chew. If we were to say, "Oh 
 yeah, do as many as you fancy. Just do 
 like a whole bunch of tasks." Then we'd 
 end up with the same issues that we get 
 when we ask the LM to do just do the 
 whole thing, which is that LMS get 
 really stupid as you add more tokens to 
 the context window and you'd produce 
 crappier code as a result. This also 
 means we need to be careful about sizing 
 the tasks, too. If we have one enormous 
 task here and then a bunch of smaller 
 tasks, then when the LLM gets to this 
 one, it's going to just be swallowed up. 
 So, when we design the PRD, we got to 
 make sure that all of the tasks are nice 
 and small to make things really as easy 
 as possible for the LLM. And to be 
 honest, this is just good practice 
 anyway. If you design massive features 
 that take huge amounts of time in your 
 sprint, you're not going to have a fun 
 time whether you're an AI or a human. 
 Now, we finally get to the end of the 
 prompt. We say if while implementing the 
 feature you notice the PRD is complete 
 output promise complete here. All of 
 this we have saved in a variable here 
 that we then echo out to the terminal. 
 We then check to see if it contains 
 promise complete here and if it does 
 then we exit out of the loop early. I've 
 also set up this nice little CLI here. 
 This is a total TypeScript CLI that says 
 notify that sends me a WhatsApp message 
 saying that it's complete after X number 
 of iterations. So that is the essence of 
 Ralph. You have a list of tasks or a 
 description of a set of tasks that you 
 need to be done. You have a progress.txt 
 file that you then append to and then 
 you run the thing in a loop with a backs 
 stop to make it stop it running 
 infinitely. However, how do you know 
 that it's going to produce working code, 
 right? How do you prevent it from just 
 running endlessly and just spitting out 
 bad stuff? Well, to make Ralph really 
 work, you really need feedback loops. 
 This is of course where Typescript comes 
 to the four, right? check that the types 
 check via PNPM type check and that the 
 unit test pass via PNPM test. Whenever 
 your Ralph loop commits, CI has to stay 
 green. One really easy way that Ralph 
 can fail is that it commits some bad 
 code and then doesn't know where the bad 
 code came from because it lost all of 
 its memory. This is another reason why 
 small tasks are good. The LLM is usually 
 really focused on that small task, able 
 to write tests that just cover that user 
 story. and keeping it focused on a small 
 change usually means it produces better 
 outputs, is able to see the feedback 
 loop just for that feature. It's just 
 better. By the way, another article you 
 should definitely read if you're 
 interested in this stuff is effective 
 harnesses for longrunning agents from 
 Anthropic. I took a lot of inspiration 
 for this article, especially in 
 progress.txt here and in the format for 
 this JSON based PRD, which is a 
 recommendation from Anthropic. Another 
 thing they recommend is absolutely 
 robust feedback loops. In the article, 
 they noticed Claude's tendency to mark a 
 feature as complete without proper 
 testing. But it did much better at 
 verifying features end to end once 
 explicitly prompted to use browser 
 automation tools and do all testing as a 
 human user would. So these feedback 
 loops are essential for the LLM knowing 
 that the code works. And again, this is 
 another reason to keep these changes 
 really small so that you still have 
 context window left for the LLM actually 
 checking that it works. Doing things 
 like hooking it up to Playright's MCP 
 server is really good but quite context 
 expensive. So you want to make sure 
 tasks are small so that you have the 
 budget to actually poke around and for 
 the LM to view images and stuff. Now so 
 far we've been talking about Ralph as an 
 asynchronous coding agent that can run 
 overnight. A kind of AFK Ralph away from 
 keyboard Ralph. But a modification we 
 can make to that is just stick a human 
 in the loop here. This is something that 
 I've been experimenting with for 
 difficult to implement features features 
 where I want to do a lot of steering of 
 the LLM. And it's also a great way to 
 learn Ralph's capabilities and 
 understand what it's doing. For this 
 setup, I have a Ralph once.sh file 
 inside my repo that I pretty often use. 
 It has pretty much exactly the same 
 prompt as the normal Ralph. Instead, it 
 just runs it in an interactive terminal 
 instead. So, let's actually do something 
 that I know you've been waiting for, 
 which is let's see it in action. I'm 
 going to run plans Ralph once.sh. We can 
 see Claude Code is running here. And the 
 first thing it's done is it's selected a 
 bunch of PRD items and it's choosing the 
 priority. By the way, I'm using Opus 
 4.5. I have Claude Max 5X and it's gone 
 for 2123 
 27. So, it's only going to do beats 
 display as three orange ellipses dots 
 below clip. And there's some nice 
 reasoning there. Without the visual 
 display working, the other beat UI items 
 can't be verified. Then, it gives itself 
 a little plan here and it's going to 
 start the implementation. Okay, we can 
 see it's create the beat indicator 
 component. It's added that into the 
 code. Then further down, we've got the 
 insertion point. Okay, there it is. 
 Added the beat indicator there. It then 
 immediately runs the type check and the 
 tests here. That all looks good. So, 
 they both passed. Does a bit more 
 verification and then it marks the PRD 
 as passes true. Once that was done, it 
 went down and edited the progress. TXT 
 file just here. And it even adds a 
 little note to itself saying, "Okay, 
 next you might want to think about this 
 PR item or maybe the beat playback 
 item." It then commits and diffs and 
 does all of its good stuff. And just so 
 I can prove to you it worked, we can 
 rightclick one of these items here and 
 press add beat. And we get this little 
 three orange dots, which looks great. So 
 yeah, I'm pretty happy with this 
 actually editing the video recording 
 software while editing a video that I'm 
 recording. Anyway, crazy. So I'm happy 
 with that. And if I want to run it again 
 and just do a few more PRD items, I just 
 run the same command again and it goes 
 through the loop again. That's something 
 you really can't underestimate with 
 Ralph is it's just so usable and easy to 
 use. Even when I'm in this human in the 
 loop version, I still feel like I'm more 
 productive than if I were to create a 
 multihase plan or something. This 
 concept of a loop where you just take 
 stuff off the board, take stuff off the 
 board and keep working is just feels so 
 familiar. and the multifphase plans that 
 I was doing before just felt really 
 ownorous to put together. Instead of 
 this kind of like really anal retentive 
 planner here, Ralph puts you in the seat 
 of the requirements gatherer. Really a 
 kind of product designer where instead 
 of focusing on how it's going to be 
 done, you just focus on what needs to be 
 done and how it should behave. And once 
 it's complete, you go through, read the 
 code, test everything works, and then 
 change the PRD if you need to. So that 
 folks is how I've been writing most of 
 my code. We have a Ralph AFK version, a 
 Ralph human the loop version and a 
 prd.json. As I learn more about this, 
 I'm going to invest more in my feedback 
 loops. With Ralph, you want more tests. 
 You want higher quality tests. You want 
 non-flaky tests. You want an MCP server 
 that can allow it to explore your 
 application. And most of all, you want 
 types, types, types, types, types. 
 Absolutely. You want the strongest types 
 you can get. Now, if you dug this stuff, 
 then you should head to aihero.dev. I've 
 been thinking about AI and talking about 
 AI and all of the stuff I've put 
 together is up here. My latest course on 
 the AI SDK allows you to learn how to 
 master AI in Typescript and it's 
 currently skinned in V5, but V6 came out 
 recently, so I'm doing a free update for 
 everyone who bought the V5 crash course. 
 But overall, thank you so much for 
 watching. This is a really fun one to 
 record and I'm recording it because I 
 just love this new style of coding. It 
 just feels so much more intuitive than 
 the stuff we were doing even 3 months 
 ago. And a final word, too. If you're 
 worried about getting left behind about 
 this stuff, if it all feels too hypy, 
 just remember that the dev branch is 
 always wackier than the main branch. We 
 are experimenting with stuff here and 
 some of it works and some of it doesn't 
 work and a lot of it changes. But in a 
 couple years time, we are going to 
 coalesce around some kind of shared 
 understanding about how to use these 
 tools effectively and that will still be 
 just as prized 2 years from now as it is 
 now. So with that, thanks for watching 
 and I will see you very soon. And the 
 fundamentals of development, which are 
 basically trying to translate people's 
 weird dreams into code, into language 
 that computers understand, that's not 
 going anywhere.