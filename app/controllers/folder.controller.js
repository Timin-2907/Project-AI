// app/controllers/folder.controller.js
const db = require('../config/db');

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Lấy path của folder từ DB.
 */
async function getFolderPath(folderId, conn) {
  const [rows] = await conn.execute(
    'SELECT FolderID, Name, ParentID, Path FROM Folder WHERE FolderID = ?',
    [folderId]
  );
  return rows[0] || null;
}

/**
 * Kiểm tra targetId có phải con cháu của folderId không.
 * Đệ quy theo ParentID để tránh vòng lặp.
 */
async function isDescendant(folderId, targetId, conn) {
  let currentId = targetId;
  const visited = new Set();

  while (currentId !== null && currentId !== undefined) {
    if (visited.has(currentId)) break;
    if (currentId === folderId) return true;
    visited.add(currentId);

    const [rows] = await conn.execute(
      'SELECT ParentID FROM Folder WHERE FolderID = ?',
      [currentId]
    );
    currentId = rows[0]?.ParentID ?? null;
  }
  return false;
}

/**
 * Cập nhật Path của folder và toàn bộ con cháu (cascade).
 * oldPrefix → newPrefix bằng REPLACE trên cột Path.
 */
async function updatePathCascade(oldPrefix, newPrefix, conn) {
  // Cập nhật folders
  await conn.execute(
    `UPDATE Folder
     SET Path = CONCAT(?, SUBSTRING(Path, LENGTH(?) + 1)),
         UpdatedAt = NOW()
     WHERE Path = ? OR Path LIKE ?`,
    [newPrefix, oldPrefix, oldPrefix, `${oldPrefix}/%`]
  );

  // Cập nhật documents trong các folder bị ảnh hưởng
  await conn.execute(
    `UPDATE Document
     SET Path = CONCAT(?, SUBSTRING(Path, LENGTH(?) + 1)),
         UpdatedAt = NOW()
     WHERE Path = ? OR Path LIKE ?`,
    [newPrefix, oldPrefix, oldPrefix, `${oldPrefix}/%`]
  );
}

// ─── Controllers ──────────────────────────────────────────────────────────────

/**
 * POST /api/folders
 * Tạo thư mục mới.
 */
const createFolder = async (req, res) => {
  const conn = await db.getConnection();
  try {
    const { name, parent_id } = req.body;
    const userId = req.user.userId;

    if (!name || !name.trim()) {
      return res.status(400).json({ success: false, message: 'Tên thư mục không được để trống' });
    }
    if (/[\\/:*?"<>|]/.test(name)) {
      return res.status(400).json({ success: false, message: 'Tên thư mục chứa ký tự không hợp lệ' });
    }

    // Kiểm tra parent tồn tại
    let parentPath = '/root';
    if (parent_id) {
      const parent = await getFolderPath(parent_id, conn);
      if (!parent) return res.status(404).json({ success: false, message: 'Thư mục cha không tồn tại' });
      parentPath = parent.Path;
    }

    // Kiểm tra trùng tên trong cùng cha
    const [dup] = await conn.execute(
      'SELECT FolderID FROM Folder WHERE ParentID <=> ? AND Name = ?',
      [parent_id ?? null, name.trim()]
    );
    if (dup.length > 0) {
      return res.status(409).json({ success: false, message: 'Đã tồn tại thư mục cùng tên trong thư mục cha' });
    }

    const path = `${parentPath}/${name.trim()}`;

    const [result] = await conn.execute(
      'INSERT INTO Folder (Name, ParentID, Path, OwnerID) VALUES (?, ?, ?, ?)',
      [name.trim(), parent_id ?? null, path, userId]
    );

    res.status(201).json({
      success: true,
      message: 'Tạo thư mục thành công',
      data: { folder_id: result.insertId, name: name.trim(), parent_id: parent_id ?? null, path },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  } finally {
    conn.release();
  }
};

/**
 * GET /api/folders
 * Danh sách thư mục gốc của user.
 */
const listRootFolders = async (req, res) => {
  try {
    const [folders] = await db.execute(
      'SELECT * FROM Folder WHERE ParentID IS NULL AND OwnerID = ? ORDER BY Name',
      [req.user.userId]
    );
    res.json({ success: true, data: folders });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

/**
 * GET /api/folders/:folderId
 * Nội dung thư mục: thư mục con + tài liệu.
 */
const getFolderContents = async (req, res) => {
  try {
    const { folderId } = req.params;

    const [folders] = await db.execute('SELECT * FROM Folder WHERE FolderID = ?', [folderId]);
    if (folders.length === 0) {
      return res.status(404).json({ success: false, message: 'Không tìm thấy thư mục' });
    }

    const [subfolders] = await db.execute(
      'SELECT * FROM Folder WHERE ParentID = ? ORDER BY Name', [folderId]
    );
    const [documents] = await db.execute(
      'SELECT * FROM Document WHERE FolderID = ? ORDER BY Name', [folderId]
    );

    res.json({
      success: true,
      data: { folder: folders[0], subfolders, documents },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

/**
 * PATCH /api/folders/:folderId/rename
 * Đổi tên thư mục + cập nhật path cascade.
 */
const renameFolder = async (req, res) => {
  const conn = await db.getConnection();
  try {
    const { folderId } = req.params;
    const { name } = req.body;
    const userId = req.user.userId;

    if (!name || !name.trim()) {
      return res.status(400).json({ success: false, message: 'Tên thư mục không được để trống' });
    }

    const folder = await getFolderPath(folderId, conn);
    if (!folder) return res.status(404).json({ success: false, message: 'Không tìm thấy thư mục' });
    if (folder.OwnerID !== userId) {
      return res.status(403).json({ success: false, message: 'Không có quyền đổi tên thư mục này' });
    }
    if (folder.Name === name.trim()) {
      return res.json({ success: true, message: 'Tên không thay đổi', data: folder });
    }

    // Kiểm tra trùng tên
    const [dup] = await conn.execute(
      'SELECT FolderID FROM Folder WHERE ParentID <=> ? AND Name = ? AND FolderID != ?',
      [folder.ParentID ?? null, name.trim(), folderId]
    );
    if (dup.length > 0) {
      return res.status(409).json({ success: false, message: 'Đã tồn tại thư mục cùng tên' });
    }

    // Tính path mới
    const parentSegment = folder.Path.substring(0, folder.Path.lastIndexOf('/'));
    const newPath = `${parentSegment}/${name.trim()}`;

    await conn.beginTransaction();
    await updatePathCascade(folder.Path, newPath, conn);
    await conn.execute(
      'UPDATE Folder SET Name = ?, UpdatedAt = NOW() WHERE FolderID = ?',
      [name.trim(), folderId]
    );
    await conn.commit();

    res.json({ success: true, message: 'Đổi tên thành công', data: { ...folder, name: name.trim(), path: newPath } });
  } catch (err) {
    await conn.rollback();
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  } finally {
    conn.release();
  }
};

/**
 * PATCH /api/folders/:folderId/move
 * ⭐ Di chuyển thư mục sang thư mục cha mới.
 *
 * Body: { target_parent_id: number | null }
 *   - null  → chuyển lên root
 *   - number → ID thư mục đích
 *
 * Xử lý:
 *   1. Validate quyền sở hữu
 *   2. Chặn di chuyển vào chính nó / con cháu
 *   3. Kiểm tra trùng tên ở đích
 *   4. Cập nhật ParentID + Path cascade (folder + tất cả con + documents)
 */
const moveFolder = async (req, res) => {
  const conn = await db.getConnection();
  try {
    const { folderId } = req.params;
    const { target_parent_id } = req.body;   // null hoặc number
    const userId = req.user.userId;

    const folderIdNum = parseInt(folderId, 10);

    // Lấy folder hiện tại
    const folder = await getFolderPath(folderIdNum, conn);
    if (!folder) {
      return res.status(404).json({ success: false, message: 'Không tìm thấy thư mục' });
    }

    // Quyền sở hữu
    if (folder.OwnerID !== userId) {
      return res.status(403).json({ success: false, message: 'Không có quyền di chuyển thư mục này' });
    }

    // Không di chuyển vào chính nó
    if (target_parent_id === folderIdNum) {
      return res.status(400).json({ success: false, message: 'Không thể di chuyển thư mục vào chính nó' });
    }

    // Không thay đổi gì
    const currentParent = folder.ParentID ?? null;
    const targetParent  = target_parent_id ?? null;
    if (currentParent === targetParent) {
      return res.json({ success: true, message: 'Thư mục đã ở vị trí này', data: folder });
    }

    // Kiểm tra target parent tồn tại + chặn di chuyển vào con cháu
    let newParentPath = '/root';
    if (targetParent !== null) {
      const targetFolder = await getFolderPath(targetParent, conn);
      if (!targetFolder) {
        return res.status(404).json({ success: false, message: 'Thư mục đích không tồn tại' });
      }

      const circular = await isDescendant(folderIdNum, targetParent, conn);
      if (circular) {
        return res.status(400).json({
          success: false,
          message: 'Không thể di chuyển thư mục vào thư mục con của nó',
        });
      }

      newParentPath = targetFolder.Path;
    }

    // Kiểm tra trùng tên ở thư mục đích
    const [dup] = await conn.execute(
      'SELECT FolderID FROM Folder WHERE ParentID <=> ? AND Name = ? AND FolderID != ?',
      [targetParent, folder.Name, folderIdNum]
    );
    if (dup.length > 0) {
      return res.status(409).json({
        success: false,
        message: `Đã tồn tại thư mục tên "${folder.Name}" trong thư mục đích`,
      });
    }

    // Path mới
    const newPath = `${newParentPath}/${folder.Name}`;

    // Transaction: cập nhật cascade
    await conn.beginTransaction();
    await updatePathCascade(folder.Path, newPath, conn);
    await conn.execute(
      'UPDATE Folder SET ParentID = ?, UpdatedAt = NOW() WHERE FolderID = ?',
      [targetParent, folderIdNum]
    );
    await conn.commit();

    res.json({
      success: true,
      message: 'Di chuyển thư mục thành công',
      data: {
        folder_id: folder.FolderID,
        name:      folder.Name,
        parent_id: targetParent,
        path:      newPath,
      },
    });
  } catch (err) {
    await conn.rollback();
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  } finally {
    conn.release();
  }
};

/**
 * DELETE /api/folders/:folderId
 * Xóa thư mục (cascade theo DB).
 */
const deleteFolder = async (req, res) => {
  try {
    const { folderId } = req.params;
    const [folders] = await db.execute('SELECT * FROM Folder WHERE FolderID = ?', [folderId]);
    if (folders.length === 0) {
      return res.status(404).json({ success: false, message: 'Không tìm thấy thư mục' });
    }
    if (folders[0].OwnerID !== req.user.userId) {
      return res.status(403).json({ success: false, message: 'Không có quyền xóa thư mục này' });
    }

    await db.execute('DELETE FROM Folder WHERE FolderID = ?', [folderId]);
    res.json({ success: true, message: 'Xóa thư mục thành công' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

module.exports = {
  createFolder,
  listRootFolders,
  getFolderContents,
  renameFolder,
  moveFolder,
  deleteFolder,
};