import type { Project, ProjectData } from './types';

const EMPTY_PROJECT: Project = {
  name: '',
  path: '',
  paper: '',
  authors: '',
  venue: '',
  capstone: '',
  lastVerified: '',
};

export const EMPTY_PROJECT_DATA: ProjectData = {
  project: EMPTY_PROJECT,
  recents: [],
  nodes: [],
  definitions: [],
  foundations: [],
  paperBlocks: [],
  leanBlocks: [],
  terms: {},
  failures: [],
  activeAgent: null,
};
