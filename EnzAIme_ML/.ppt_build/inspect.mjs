import fs from 'node:fs/promises';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('C:/Users/Welcome/Downloads/ProjectReview_EnzymeDE_Updated.pptx'));
console.log('slides',p.slides.items.length);
console.log((await p.inspect({kind:'layout',maxChars:2500})).ndjson);
console.log('collections',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)));
console.log('shapes',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides.items[1].shapes)));
await fs.writeFile('.ppt_build/imported_layout.json',await (await p.slides.items[1].export({format:'layout'})).text());
await fs.writeFile('.ppt_build/imported_preview.png',new Uint8Array(await (await p.slides.items[1].export({format:'png',scale:1})).arrayBuffer()));
