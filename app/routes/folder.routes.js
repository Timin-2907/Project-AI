// app/routes/folder.routes.js
const express = require('express');
const router = express.Router();
const { authenticate } = require('../middlewares/auth.middleware');
const {
  createFolder,
  listRootFolders,
  getFolderContents,
  renameFolder,
  moveFolder,
  deleteFolder,
} = require('../controllers/folder.controller');

/**
 * @route   POST /api/folders
 * @desc    Tạo thư mục mới
 * @body    { name: string, parent_id?: number }
 * @access  Private
 */
router.post('/', authenticate, createFolder);

/**
 * @route   GET /api/folders
 * @desc    Danh sách thư mục gốc của user
 * @access  Private
 */
router.get('/', authenticate, listRootFolders);

/**
 * @route   GET /api/folders/:folderId
 * @desc    Nội dung thư mục (sub-folders + documents)
 * @access  Private
 */
router.get('/:folderId', authenticate, getFolderContents);

/**
 * @route   PATCH /api/folders/:folderId/rename
 * @desc    Đổi tên thư mục (cascade cập nhật path con cháu)
 * @body    { name: string }
 * @access  Private
 */
router.patch('/:folderId/rename', authenticate, renameFolder);

/**
 * @route   PATCH /api/folders/:folderId/move
 * @desc    ⭐ Di chuyển thư mục sang vị trí mới
 * @body    { target_parent_id: number | null }
 * @access  Private
 */
router.patch('/:folderId/move', authenticate, moveFolder);

/**
 * @route   DELETE /api/folders/:folderId
 * @desc    Xóa thư mục (cascade)
 * @access  Private
 */
router.delete('/:folderId', authenticate, deleteFolder);

module.exports = router;