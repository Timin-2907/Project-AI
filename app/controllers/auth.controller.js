const bcrypt = require('bcryptjs');
const crypto = require('crypto');
const db = require('../config/db');
const { generateAccessToken, generateRefreshToken, verifyRefreshToken } = require('../utils/jwt');
const { sendVerificationEmail, sendPasswordResetEmail } = require('../utils/email');

// ─── Helper ──────────────────────────────────────────────────────────────────
const generateOTP = () => Math.floor(100000 + Math.random() * 900000).toString();

// ─── ĐĂNG KÝ ─────────────────────────────────────────────────────────────────
// POST /api/auth/register
const register = async (req, res) => {
  const conn = await db.getConnection();
  try {
    const { username, email, password } = req.body;

    // Kiểm tra trùng
    const [exists] = await conn.execute(
      'SELECT UserID FROM User WHERE Email = ? OR Username = ?',
      [email, username]
    );
    if (exists.length > 0) {
      return res.status(409).json({ success: false, message: 'Email hoặc username đã tồn tại' });
    }

    const passwordHash = await bcrypt.hash(password, 12);

    await conn.beginTransaction();

    // Tạo user
    const [result] = await conn.execute(
      'INSERT INTO User (Username, Email, PasswordHash, RoleID, Status) VALUES (?, ?, ?, 1, "inactive")',
      [username, email, passwordHash]
    );
    const userId = result.insertId;

    // Tạo OTP
    const code = generateOTP();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 phút
    await conn.execute(
      'INSERT INTO Verification (UserID, Code, ExpiresAt, Status) VALUES (?, ?, ?, "pending")',
      [userId, code, expiresAt]
    );

    await conn.commit();

    // Gửi email (không block response nếu lỗi email)
    try {
      await sendVerificationEmail(email, code);
    } catch (emailErr) {
      console.error('Email error:', emailErr.message);
    }

    res.status(201).json({
      success: true,
      message: 'Đăng ký thành công. Vui lòng kiểm tra email để xác minh tài khoản.',
      data: { userId, email },
    });
  } catch (err) {
    await conn.rollback();
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  } finally {
    conn.release();
  }
};

// ─── XÁC MINH EMAIL ──────────────────────────────────────────────────────────
// POST /api/auth/verify-email
const verifyEmail = async (req, res) => {
  try {
    const { email, code } = req.body;

    const [users] = await db.execute('SELECT UserID, Status FROM User WHERE Email = ?', [email]);
    if (users.length === 0) return res.status(404).json({ success: false, message: 'Không tìm thấy tài khoản' });

    const user = users[0];
    if (user.Status === 'active') {
      return res.status(400).json({ success: false, message: 'Tài khoản đã được xác minh' });
    }

    const [verifications] = await db.execute(
      'SELECT * FROM Verification WHERE UserID = ? AND Code = ? AND Status = "pending" AND ExpiresAt > NOW() ORDER BY VerificationID DESC LIMIT 1',
      [user.UserID, code]
    );
    if (verifications.length === 0) {
      return res.status(400).json({ success: false, message: 'Mã xác minh không hợp lệ hoặc đã hết hạn' });
    }

    await db.execute('UPDATE User SET Status = "active" WHERE UserID = ?', [user.UserID]);
    await db.execute('UPDATE Verification SET Status = "verified" WHERE VerificationID = ?', [verifications[0].VerificationID]);

    res.json({ success: true, message: 'Xác minh tài khoản thành công. Bạn có thể đăng nhập.' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── GỬI LẠI MÃ XÁC MINH ────────────────────────────────────────────────────
// POST /api/auth/resend-verification
const resendVerification = async (req, res) => {
  try {
    const { email } = req.body;
    const [users] = await db.execute('SELECT UserID, Status FROM User WHERE Email = ?', [email]);
    if (users.length === 0) return res.status(404).json({ success: false, message: 'Không tìm thấy tài khoản' });

    const user = users[0];
    if (user.Status === 'active') {
      return res.status(400).json({ success: false, message: 'Tài khoản đã được xác minh' });
    }

    const code = generateOTP();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000);
    await db.execute(
      'INSERT INTO Verification (UserID, Code, ExpiresAt, Status) VALUES (?, ?, ?, "pending")',
      [user.UserID, code, expiresAt]
    );

    await sendVerificationEmail(email, code);
    res.json({ success: true, message: 'Mã xác minh mới đã được gửi' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── ĐĂNG NHẬP ───────────────────────────────────────────────────────────────
// POST /api/auth/login
const login = async (req, res) => {
  try {
    const { email, password } = req.body;

    const [users] = await db.execute(
      'SELECT u.UserID, u.Username, u.Email, u.PasswordHash, u.Status, r.RoleName FROM User u JOIN Role r ON u.RoleID = r.RoleID WHERE u.Email = ?',
      [email]
    );
    if (users.length === 0) {
      return res.status(401).json({ success: false, message: 'Email hoặc mật khẩu không đúng' });
    }

    const user = users[0];

    if (user.Status === 'inactive') {
      return res.status(403).json({ success: false, message: 'Tài khoản chưa được xác minh. Vui lòng kiểm tra email.' });
    }
    if (user.Status === 'banned') {
      return res.status(403).json({ success: false, message: 'Tài khoản đã bị khóa' });
    }

    const isMatch = await bcrypt.compare(password, user.PasswordHash);

    // Ghi lịch sử đăng nhập
    await db.execute(
      'INSERT INTO LoginHistory (UserID, Status) VALUES (?, ?)',
      [user.UserID, isMatch ? 'success' : 'failed']
    );

    if (!isMatch) {
      return res.status(401).json({ success: false, message: 'Email hoặc mật khẩu không đúng' });
    }

    const payload = { userId: user.UserID, email: user.Email, role: user.RoleName };
    const accessToken = generateAccessToken(payload);
    const refreshToken = generateRefreshToken(payload);

    // Lưu refresh token
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
    await db.execute(
      'INSERT INTO AuthToken (UserID, Token, ExpiresAt) VALUES (?, ?, ?)',
      [user.UserID, refreshToken, expiresAt]
    );

    res.json({
      success: true,
      message: 'Đăng nhập thành công',
      data: {
        accessToken,
        refreshToken,
        user: { id: user.UserID, username: user.Username, email: user.Email, role: user.RoleName },
      },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── REFRESH TOKEN ────────────────────────────────────────────────────────────
// POST /api/auth/refresh-token
const refreshToken = async (req, res) => {
  try {
    const { refreshToken: token } = req.body;
    if (!token) return res.status(400).json({ success: false, message: 'Thiếu refresh token' });

    const [tokens] = await db.execute(
      'SELECT * FROM AuthToken WHERE Token = ? AND ExpiresAt > NOW()',
      [token]
    );
    if (tokens.length === 0) {
      return res.status(401).json({ success: false, message: 'Refresh token không hợp lệ hoặc đã hết hạn' });
    }

    const decoded = verifyRefreshToken(token);
    const newAccessToken = generateAccessToken({ userId: decoded.userId, email: decoded.email, role: decoded.role });

    res.json({ success: true, data: { accessToken: newAccessToken } });
  } catch (err) {
    res.status(401).json({ success: false, message: 'Refresh token không hợp lệ' });
  }
};

// ─── ĐĂNG XUẤT ───────────────────────────────────────────────────────────────
// POST /api/auth/logout
const logout = async (req, res) => {
  try {
    const { refreshToken: token } = req.body;
    if (token) {
      await db.execute('DELETE FROM AuthToken WHERE Token = ?', [token]);
    }
    res.json({ success: true, message: 'Đăng xuất thành công' });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── QUÊN MẬT KHẨU ───────────────────────────────────────────────────────────
// POST /api/auth/forgot-password
const forgotPassword = async (req, res) => {
  try {
    const { email } = req.body;
    const [users] = await db.execute('SELECT UserID FROM User WHERE Email = ?', [email]);

    // Luôn trả về 200 để tránh lộ thông tin email tồn tại
    if (users.length === 0) {
      return res.json({ success: true, message: 'Nếu email tồn tại, link đặt lại mật khẩu sẽ được gửi' });
    }

    const user = users[0];
    const resetToken = crypto.randomBytes(32).toString('hex');
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 phút

    await db.execute(
      'INSERT INTO PasswordReset (UserID, ResetToken, ExpiresAt) VALUES (?, ?, ?)',
      [user.UserID, resetToken, expiresAt]
    );

    const resetLink = `${process.env.CLIENT_URL}/reset-password?token=${resetToken}`;
    await sendPasswordResetEmail(email, resetLink);

    res.json({ success: true, message: 'Nếu email tồn tại, link đặt lại mật khẩu sẽ được gửi' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── ĐẶT LẠI MẬT KHẨU ───────────────────────────────────────────────────────
// POST /api/auth/reset-password
const resetPassword = async (req, res) => {
  try {
    const { token, password } = req.body;

    const [resets] = await db.execute(
      'SELECT * FROM PasswordReset WHERE ResetToken = ? AND ExpiresAt > NOW() ORDER BY ResetID DESC LIMIT 1',
      [token]
    );
    if (resets.length === 0) {
      return res.status(400).json({ success: false, message: 'Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn' });
    }

    const passwordHash = await bcrypt.hash(password, 12);
    await db.execute('UPDATE User SET PasswordHash = ? WHERE UserID = ?', [passwordHash, resets[0].UserID]);
    await db.execute('DELETE FROM PasswordReset WHERE UserID = ?', [resets[0].UserID]);

    res.json({ success: true, message: 'Mật khẩu đã được đặt lại thành công' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── LẤY THÔNG TIN NGƯỜI DÙNG HIỆN TẠI ──────────────────────────────────────
// GET /api/auth/me
const getMe = async (req, res) => {
  try {
    const [users] = await db.execute(
      'SELECT u.UserID, u.Username, u.Email, u.Status, u.CreatedAt, r.RoleName FROM User u JOIN Role r ON u.RoleID = r.RoleID WHERE u.UserID = ?',
      [req.user.userId]
    );
    if (users.length === 0) return res.status(404).json({ success: false, message: 'Không tìm thấy người dùng' });

    const user = users[0];
    res.json({
      success: true,
      data: { id: user.UserID, username: user.Username, email: user.Email, role: user.RoleName, status: user.Status, createdAt: user.CreatedAt },
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

// ─── LỊCH SỬ ĐĂNG NHẬP ───────────────────────────────────────────────────────
// GET /api/auth/login-history
const getLoginHistory = async (req, res) => {
  try {
    const [history] = await db.execute(
      'SELECT HistoryID, Status, LoginAt FROM LoginHistory WHERE UserID = ? ORDER BY LoginAt DESC LIMIT 20',
      [req.user.userId]
    );
    res.json({ success: true, data: history });
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, message: 'Lỗi server' });
  }
};

module.exports = {
  register,
  verifyEmail,
  resendVerification,
  login,
  refreshToken,
  logout,
  forgotPassword,
  resetPassword,
  getMe,
  getLoginHistory,
};