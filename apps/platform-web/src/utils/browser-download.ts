export function downloadBlob(blob: Blob, filename: string) {
  if (typeof document === 'undefined') {
    return
  }

  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
