import fs from 'node:fs/promises';
import {FileBlob, PresentationFile} from '@oai/artifact-tool';
const p=await PresentationFile.importPptx(await FileBlob.load('C:/Users/Welcome/Downloads/PET_Degradation_Overview.pptx'));
await fs.mkdir('.ppt_build/mentor_review',{recursive:true});
console.log('Slides',p.slides.items.length);
for(const n of [1,3,17,21,22,27,35,43,48,55,59,65,70,76]){
 if(n>p.slides.items.length)continue;
 await fs.writeFile(`.ppt_build/mentor_review/slide-${n}.png`,new Uint8Array(await (await p.slides.items[n-1].export({format:'png',scale:0.8})).arrayBuffer()));
 console.log('Rendered',n);
}
