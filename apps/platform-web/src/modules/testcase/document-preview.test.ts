import { describe, expect, it } from 'vitest'
import { resolveDocumentContentType, resolveDocumentStoragePath } from '@/modules/testcase/document-preview'
import type { TestcaseDocument } from '@/types/management'

function buildDocument(overrides: Partial<TestcaseDocument> = {}): TestcaseDocument {
  return {
    id: 'doc-1',
    project_id: 'project-1',
    batch_id: 'batch-1',
    filename: 'document.pdf',
    content_type: 'application/pdf',
    storage_path: 'assets/document.pdf',
    source_kind: 'upload',
    parse_status: 'parsed',
    summary_for_model: '',
    parsed_text: null,
    structured_data: null,
    provenance: {},
    confidence: null,
    error: null,
    created_at: '2026-04-21T00:00:00Z',
    ...overrides
  }
}

describe('document preview helpers', () => {
  it('falls back to provenance asset metadata when top-level fields are missing', () => {
    const document = buildDocument({
      content_type: '',
      storage_path: null,
      provenance: {
        asset: {
          content_type: 'application/pdf',
          storage_path: 'legacy/document.pdf'
        }
      }
    })

    expect(resolveDocumentContentType(document)).toBe('application/pdf')
    expect(resolveDocumentStoragePath(document)).toBe('legacy/document.pdf')
  })

  it('guesses content type from filename when metadata is missing', () => {
    const document = buildDocument({
      filename: 'legacy-image.jpeg',
      content_type: '',
      storage_path: null,
      provenance: {}
    })

    expect(resolveDocumentContentType(document)).toBe('image/jpeg')
  })
})

