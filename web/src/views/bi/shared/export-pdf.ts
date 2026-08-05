import { jsPDF } from 'jspdf';

const PAGE_WIDTH = 210; // A4 mm
const PAGE_HEIGHT = 297;
const MARGIN = 12;

const FALLBACK_W = 800;
const FALLBACK_H = 400;

export interface ChartPdfItem {
  title: string;
  dataUrl: string;
}

/** 把标题文本渲染成 PNG dataURL（浏览器系统字体，支持中文）— jsPDF 内置字体不含 CJK 字形。 */
function renderTitleImage(title: string): string {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) return '';
  const fontSize = 32;
  ctx.font = `600 ${fontSize}px system-ui, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif`;
  const width = Math.ceil(ctx.measureText(title || 'Chart').width) + 24;
  canvas.width = width;
  canvas.height = fontSize + 24;
  const ctx2 = canvas.getContext('2d');
  if (!ctx2) return '';
  ctx2.font = ctx.font;
  ctx2.textBaseline = 'middle';
  ctx2.fillStyle = '#1f1f1f';
  ctx2.fillText(title || 'Chart', 12, canvas.height / 2);
  return canvas.toDataURL('image/png');
}

/** 加载 dataURL 图片的实际像素尺寸，用于 PDF 内等比缩放。 */
function loadImageSize(dataUrl: string): Promise<{ width: number; height: number }> {
  return new Promise(resolve => {
    const img = new Image();
    img.addEventListener('load', () =>
      resolve({
        width: img.naturalWidth || FALLBACK_W,
        height: img.naturalHeight || FALLBACK_H
      })
    );
    img.addEventListener('error', () => resolve({ width: FALLBACK_W, height: FALLBACK_H }));
    img.src = dataUrl;
  });
}

function pageFooter(doc: jsPDF, pageNo: number) {
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(`Page ${pageNo}`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 8, { align: 'right' });
}

async function addChartPage(doc: jsPDF, title: string, dataUrl: string, pageNo: number) {
  const { width: naturalW, height: naturalH } = await loadImageSize(dataUrl);
  const maxW = PAGE_WIDTH - MARGIN * 2;
  const maxH = PAGE_HEIGHT - MARGIN * 2 - 18;
  const scale = Math.min(maxW / naturalW, maxH / naturalH);
  const w = naturalW * scale;
  const h = naturalH * scale;
  const x = (PAGE_WIDTH - w) / 2;
  const y = MARGIN + 14;

  // 标题以图片形式插入，避免 jsPDF 内置字体渲染中文乱码
  const titleImg = renderTitleImage(title);
  if (titleImg) {
    const tSize = await loadImageSize(titleImg);
    const tScale = Math.min(maxW / tSize.width, 12 / tSize.height);
    const tw = tSize.width * tScale;
    const th = tSize.height * tScale;
    doc.addImage(titleImg, 'PNG', (PAGE_WIDTH - tw) / 2, MARGIN, tw, th);
  }

  doc.addImage(dataUrl, 'PNG', x, y, w, h);
  pageFooter(doc, pageNo);
}

/**
 * 单图表 PDF：一张图表图片一页。
 * @param title 图表名（作为 PDF 文件名 + 页内标题）
 * @param dataUrl ECharts getDataURL 结果（data:image/png;base64,...）
 */
export async function exportChartPdf(title: string, dataUrl: string) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  await addChartPage(doc, title, dataUrl, 1);
  doc.save(`${title}.pdf`);
}

/**
 * 仪表盘 PDF：多图表逐页拼接。
 * @param title 仪表盘名
 * @param items 每个图表 { title, dataUrl }
 */
export async function exportDashboardPdf(title: string, items: ChartPdfItem[]) {
  if (!items.length) return;
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  for (let i = 0; i < items.length; i++) {
    if (i > 0) doc.addPage();
    await addChartPage(doc, items[i].title, items[i].dataUrl, i + 1);
  }
  doc.save(`${title}.pdf`);
}
