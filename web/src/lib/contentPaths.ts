import { resolve } from 'node:path';

/** All server-rendered pages and browser assets use the selected publication. */
export const contentRoot = () => resolve(process.env.ITHILDIN_CONTENT_DIR || '../content');
