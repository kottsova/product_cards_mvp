import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
import fs from 'node:fs/promises';
import path from 'node:path';
const input=process.argv[2], output=process.argv[3];
await fs.mkdir(output,{recursive:true});
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const inventory=await book.inspect({kind:'sheet',include:'id,name',maxChars:20000});
await fs.writeFile(path.join(output,'artifact_inventory.json'),JSON.stringify(inventory,null,2));
const names=inventory.ndjson.split('\n').filter(Boolean).map(line=>JSON.parse(line)).filter(row=>row.name).map(row=>row.name);
const rendered=[];
for (const [index,name] of names.entries()) {
 const preview=await book.render({sheetName:name,range:'A1:H4',scale:1,format:'png'});
 const file=path.join(output,'sheet_'+String(index+1).padStart(2,'0')+'.png');
 await fs.writeFile(file,new Uint8Array(await preview.arrayBuffer()));
 rendered.push({sheet:name,file});console.log('RENDERED',name);
}
await fs.writeFile(path.join(output,'renders.json'),JSON.stringify(rendered,null,2));
console.log('Native workbook read-only render QA',rendered.length,'sheets');
