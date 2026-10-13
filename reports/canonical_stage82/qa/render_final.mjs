import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const require=createRequire(import.meta.url);
const entry=require.resolve('@oai/artifact-tool',{paths:[path.resolve('reports/cross_brand_stage81/qa')]});
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(entry).href);
const input='reports/canonical_stage82/Canonical_Stage82.xlsx';
const output='reports/canonical_stage82/qa/final_excel';
await fs.mkdir(output,{recursive:true});
const bytes=await fs.readFile(input);
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const names=['Игровые консоли','Гарнитуры','Смартфоны','Исходные поля и mapping'];
const rendered=[];
for(const [index,name] of names.entries()){
 const png=await book.render({sheetName:name,range:'A1:H4',scale:1,format:'png'});
 const file=path.join(output,'sheet_'+String(index+1)+'.png');
 await fs.writeFile(file,new Uint8Array(await png.arrayBuffer()));rendered.push({sheet:name,file});
}
await fs.writeFile(path.join(output,'renders.json'),JSON.stringify({mode:'read-only final workbook QA',workbook_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),rendered},null,2));
console.log('Final workbook read-only previews saved',rendered.length);
