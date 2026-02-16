/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  apiSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Navigation',
      items: ['api/navigation'],
    },
    {
      type: 'category',
      label: 'DOM Reading',
      items: ['api/dom-reading'],
    },
    {
      type: 'category',
      label: 'Interaction',
      items: ['api/interaction'],
    },
    {
      type: 'category',
      label: 'Scrolling',
      items: ['api/scrolling'],
    },
    {
      type: 'category',
      label: 'Keyboard',
      items: ['api/keyboard'],
    },
    {
      type: 'category',
      label: 'Tab Management',
      items: ['api/tabs'],
    },
    {
      type: 'category',
      label: 'Screenshot',
      items: ['api/screenshot'],
    },
    {
      type: 'category',
      label: 'File & Download',
      items: ['api/file-download'],
    },
    {
      type: 'category',
      label: 'Page State',
      items: ['api/page-state'],
    },
    {
      type: 'category',
      label: 'Browser Control',
      items: ['api/control'],
    },
  ],
};

export default sidebars;
