// src/config/brandingConfig.ts

import brandingOverride from './brandingOverride';

// Define default branding configuration
const defaultConfig = {
  companyName: 'AnythingChat Inc.',
  deploymentName: 'AnythingChat',
  socialLinks: {
    twitter: { enabled: true, url: 'https://twitter.com/anythingchat' },
    github: {
      enabled: true,
      url: 'https://github.com/AnythingChat/AnythingChat',
    },
    discord: { enabled: true, url: 'https://discord.gg/anythingchat' },
  },
  navbar: {
    appName: 'AnythingChat',
    showDocsButton: true,
    menuItems: {
      home: true,
      documents: true,
      collections: true,
      chat: true,
      search: true,
      users: true,
      logs: true,
      analytics: false,
      settings: true,
    },
  },
  logo: {
    src: '/images/sciphi.svg',
    alt: 'sciphi.svg',
  },
  theme: 'dark',
  homePage: {
    pythonSdk: true,
    githubCard: true,
    hatchetCard: true,
  },
  nextConfig: {
    additionalRemoteDomain: '',
  },
};

// ✅ Declare `window.__BRANDING_CONFIG__` globally to avoid TypeScript errors
declare global {
  interface Window {
    __BRANDING_CONFIG__?: Partial<typeof defaultConfig>;
  }
}

// ✅ Load user-defined config from `window.__BRANDING_CONFIG__` (if available)
const userConfig =
  (typeof window !== 'undefined' && window.__BRANDING_CONFIG__) || {};

// ✅ Merge `defaultConfig`, `brandingOverride.ts`, and `userConfig`
export const brandingConfig = {
  ...defaultConfig,
  ...brandingOverride,
  ...userConfig,
};
