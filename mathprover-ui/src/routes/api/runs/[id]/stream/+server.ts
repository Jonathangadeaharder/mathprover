import type { RequestHandler } from './$types';
import { ProjectRootError, readLogTail, readRuns, resolveRootFromRequest } from '$lib/server/dispatch';

export const GET: RequestHandler = async ({ url, params }) => {
  let root: string;
  try {
    root = resolveRootFromRequest(url);
  } catch (err) {
    if (err instanceof ProjectRootError) return new Response(err.message, { status: 400 });
    throw err;
  }

  const runs = await readRuns(root);
  const run = runs.find((r) => r.id === params.id);
  if (!run) return new Response('run not found', { status: 404 });

  let offset = 0;
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };

      send('run', run);

      while (true) {
        const { text, size } = await readLogTail(root, run.log_path, offset);
        if (text) {
          send('log', { chunk: text, size });
          offset = size;
        }

        const fresh = (await readRuns(root)).find((r) => r.id === params.id);
        if (fresh && fresh.status !== 'running' && fresh.status !== 'pending') {
          send('done', fresh);
          controller.close();
          return;
        }

        await new Promise((r) => setTimeout(r, 1000));
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
};
