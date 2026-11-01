const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
const code = source.slice(source.indexOf('async function openTask('), source.indexOf('\nfunction option('));
function fixture() {
 const pending = new Map();
 const S = {taskRequest: 0, dirty: false, task: {id: 'old'}};
 const context = {S, api: url => new Promise(resolve => pending.set(url.split('/').at(-1), resolve)),
  save: async () => {S.dirty = false; return true;}, clearTimeout, renderTask(){}, setView(){}, renderQueue(){}, toast(){}};
 vm.createContext(context);vm.runInContext(code, context);
 return {context,S,pending};
}
(async () => {
 let f=fixture();const a=f.context.openTask('a'),b=f.context.openTask('b');
 f.pending.get('b')({id:'b'});await b;f.pending.get('a')({id:'a'});await a;
 assert.equal(f.S.task.id,'b','late response must not replace latest selected task');
 f=fixture();const c=f.context.openTask('c');f.S.taskRequest++;f.pending.get('c')({id:'c'});await c;
 assert.equal(f.S.task.id,'old','leaving the batch cancels pending task selection');
 f=fixture();const d=f.context.openTask('d');f.S.dirty=true;f.context.save=async()=>false;
 f.pending.get('d')({id:'d'});await d;
 assert.equal(f.S.task.id,'old','edits made while loading must not be discarded');
 assert.equal(f.S.dirty,true);
 console.log('3 task-navigation regression tests passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
