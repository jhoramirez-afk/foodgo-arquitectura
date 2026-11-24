const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const folder = path.join(__dirname,'..','eft');
const files = fs.readdirSync(folder).filter(n=>n.endsWith('.postman_collection.json'));
let scripts=0, requests=0;
function walk(items, fn) {for(const i of items){if(i.request) fn(i);if(i.item)walk(i.item,fn);}}
for(const name of files){
 const c=JSON.parse(fs.readFileSync(path.join(folder,name),'utf8'));
 assert.equal(c.info.schema,'https://schema.getpostman.com/json/collection/v2.1.0/collection.json');
 assert.equal(c.protocolProfileBehavior.followRedirects,false);
 function check(events){for(const e of events||[]){new vm.Script(e.script.exec.join('\n'));scripts++;}}
 check(c.event);walk(c.item,i=>{requests++;check(i.event);assert(i.request.url);if(i.request.body?.mode==='raw')JSON.parse(i.request.body.raw);});
}
const aws=JSON.parse(fs.readFileSync(path.join(folder,'FoodGo-EFT-AWS.postman_collection.json'),'utf8'));
const wait=aws.item[2].item[2].event.find(e=>e.listen==='test').script.exec.join('\n');
function execute(rows,count=0,code=200){
 const vars=new Map([['evento_id','evento-actual'],['notificacion_id','6'],['consultas_evento',count]]);
 let next='sin cambio';const failures=[],names=[];
 function expect(actual){
  const x={eql(v){assert.deepEqual(actual,v);return x;},lengthOf(v){assert.equal(actual.length,v);return x;},include(v){assert(actual.includes(v));return x;},an(v){assert.equal(Array.isArray(actual)?'array':typeof actual,v);return x;}};
  for(const k of ['to','have','be'])Object.defineProperty(x,k,{get(){return x;}});
  return x;
 }
 const pm={test(n,fn){names.push(n);try{fn();}catch(e){failures.push(n);}},expect,
   response:{code,json(){return rows;},to:{have:{status(c){assert.equal(code,c);}}}},
   collectionVariables:{get:k=>vars.get(k),set:(k,v)=>vars.set(k,v),unset:k=>vars.delete(k)},
   info:{requestId:'peticion-05'},execution:{setNextRequest:n=>next=n}};
 vm.runInNewContext(wait,{pm,console:{log(){}}});
 return {next,failures,names,count:vars.get('consultas_evento')};
}
const ok={eventoId:'evento-actual',resultado:'ENVIADO',detalle:'Simulación académica: aviso procesado'};
const pending=execute([]);assert.equal(pending.next,'peticion-05');assert.equal(pending.failures.length,0);assert.equal(pending.count,1);
const expired=execute([],29);assert.equal(expired.next,null);assert.equal(expired.failures.length,1);
const success=execute([ok],2);assert.equal(success.failures.length,0);assert(success.names.includes('Un intento del mismo evento antes del límite'));assert.equal(success.count,undefined);assert.equal(success.next,'sin cambio');
const duplicate=execute([ok,ok]);assert.equal(duplicate.failures.length,1);assert.equal(duplicate.next,null);
const wrong=execute([{...ok,resultado:'ERROR'}]);assert.equal(wrong.failures.length,1);assert.equal(wrong.next,null);
const http=execute([],0,500);assert.equal(http.failures.length,1);assert.equal(http.next,null);
const crud=JSON.parse(fs.readFileSync(path.join(folder,'FoodGo-EFT-CRUD-Usuarios.postman_collection.json'),'utf8'));
const guard=crud.item[0].item[2].event.find(e=>e.listen==='prerequest').script.exec.join('\n');
let skipped=false;vm.runInNewContext(guard,{pm:{collectionVariables:{get:()=> '123'},execution:{skipRequest(){skipped=true;}}}});assert.equal(skipped,false);
assert.throws(()=>vm.runInNewContext(guard,{pm:{collectionVariables:{get:()=> ''},execution:{skipRequest(){skipped=true;}}}}));assert.equal(skipped,true);
const report={estado:'CORRECTO',tipo:'Validación local de JSON, sintaxis y flujo simulado; no son peticiones HTTP',colecciones:files.length,peticionesDefinidas:requests,scriptsCompilados:scripts,casosDeEspera:['pendiente reintenta','límite agotado falla','un ENVIADO confirma','duplicados fallan','estado distinto falla','HTTP no exitoso falla'],proteccionCRUD:'ID propio requerido antes de operaciones dependientes',ensayoConBackend:'PENDIENTE'};
const evidence=path.join(__dirname,'..','..','evidencias');
fs.mkdirSync(evidence,{recursive:true});
fs.writeFileSync(path.join(evidence,'postman-eft-estatica.json'),JSON.stringify(report,null,2),'utf8');
console.log(JSON.stringify(report,null,2));
