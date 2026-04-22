import type { Sub2apiTemplateDetail, Sub2apiTemplateItem } from '@/modules/examples/ui-assets-catalog'

type SourceLoader = () => Promise<string>

const pageLoaders = import.meta.glob(
  [
    '../../../examples/sub2api-reference/src/views/**/*.vue',
    '!../../../examples/sub2api-reference/src/**/__tests__/**'
  ],
  {
    query: '?raw',
    import: 'default'
  }
) as Record<string, SourceLoader>

const componentLoaders = import.meta.glob(
  [
    '../../../examples/sub2api-reference/src/components/**/*.{vue,ts}',
    '!../../../examples/sub2api-reference/src/**/__tests__/**'
  ],
  {
    query: '?raw',
    import: 'default'
  }
) as Record<string, SourceLoader>

const engineeringLoaders = import.meta.glob(
  [
    '../../../examples/sub2api-reference/src/App.vue',
    '../../../examples/sub2api-reference/src/main.ts',
    '../../../examples/sub2api-reference/src/api/**/*.ts',
    '../../../examples/sub2api-reference/src/composables/**/*.ts',
    '../../../examples/sub2api-reference/src/i18n/**/*.ts',
    '../../../examples/sub2api-reference/src/router/**/*.ts',
    '../../../examples/sub2api-reference/src/stores/**/*.ts',
    '../../../examples/sub2api-reference/src/styles/**/*.css',
    '../../../examples/sub2api-reference/src/types/**/*.ts',
    '../../../examples/sub2api-reference/src/utils/**/*.ts',
    '../../../examples/sub2api-reference/src/views/**/*.ts',
    '!../../../examples/sub2api-reference/src/**/__tests__/**',
    '!../../../examples/sub2api-reference/src/**/*.d.ts'
  ],
  {
    query: '?raw',
    import: 'default'
  }
) as Record<string, SourceLoader>

const loaderMap = new Map<string, SourceLoader>([
  ...Object.entries(pageLoaders),
  ...Object.entries(componentLoaders),
  ...Object.entries(engineeringLoaders)
])

function toLoaderKey(item: Sub2apiTemplateItem) {
  return `../../../examples/sub2api-reference/src/${item.shortSource.replace(/^src\//, '')}`
}

function extractImports(code: string) {
  const imports = new Set<string>()
  const pattern = /import\s+(?:type\s+)?[\s\S]*?\sfrom\s+['"]([^'"]+)['"]/g

  for (const match of code.matchAll(pattern)) {
    const value = match[1]?.trim()
    if (value) {
      imports.add(value)
    }
  }

  return Array.from(imports)
}

function extractVueBlock(code: string, blockName: 'template' | 'script' | 'style') {
  const pattern = new RegExp(`<${blockName}[^>]*>([\\s\\S]*?)<\\/${blockName}>`)
  const match = code.match(pattern)

  return match?.[1]?.trim()
}

export async function loadSub2apiTemplateDetail(item: Sub2apiTemplateItem): Promise<Sub2apiTemplateDetail> {
  const loader = loaderMap.get(toLoaderKey(item))

  if (!loader) {
    throw new Error(`未找到模板源码加载器: ${item.shortSource}`)
  }

  const code = await loader()
  const imports = extractImports(code)

  return {
    code,
    lineCount: code.split('\n').length,
    imports,
    blocks: item.source.endsWith('.vue')
      ? {
          template: extractVueBlock(code, 'template'),
          script: extractVueBlock(code, 'script'),
          style: extractVueBlock(code, 'style')
        }
      : {},
    tags: item.tags,
    borrow: item.borrow
  }
}
