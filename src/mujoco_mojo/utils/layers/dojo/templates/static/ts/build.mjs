import * as esbuild from 'esbuild';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, 'src');
const outDir = join(__dirname, '..', 'js');

const entries = [
  { in: 'store.ts',        out: 'main.js' },
  { in: 'monitor.ts',      out: 'monitor.js' },
  { in: 'mosaic.ts',       out: 'mosaic.js' },
  { in: 'trial-viewer.ts', out: 'trial-viewer.js' },
];

const isWatch = process.argv.includes('--watch');

if (isWatch) {
  const contexts = await Promise.all(
    entries.map(({ in: inFile, out: outFile }) =>
      esbuild.context({
        entryPoints: [join(srcDir, inFile)],
        outfile: join(outDir, outFile),
        bundle: true,
        sourcemap: true,
        target: 'es2020',
        format: 'iife',
        platform: 'browser',
      }),
    ),
  );
  await Promise.all(contexts.map((ctx) => ctx.watch()));
  console.log('Watching for changes...');
} else {
  await Promise.all(
    entries.map(async ({ in: inFile, out: outFile }) => {
      await esbuild.build({
        entryPoints: [join(srcDir, inFile)],
        outfile: join(outDir, outFile),
        bundle: true,
        sourcemap: true,
        target: 'es2020',
        format: 'iife',
        platform: 'browser',
      });
      console.log(`✓ src/${inFile} → js/${outFile}`);
    }),
  );
}
