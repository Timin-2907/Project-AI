const express = require('express');
const router = express.Router();
const rateLimit = require('express-rate-limit');

const {
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
} = require('../controllers/auth.controller');

const { authenticate } = require('../middlewares/auth.middleware');
const {
  registerValidation,
  loginValidation,
  resetPasswordValidation,
} = require('../middlewares/validate.middleware');

// Rate limiters
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 phút
  max: 10,
  message: { success: false, message: 'Quá nhiều lần thử đăng nhập. Vui lòng thử lại sau 15 phút.' },
});

const forgotPasswordLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 giờ
  max: 3,
  message: { success: false, message: 'Quá nhiều yêu cầu đặt lại mật khẩu. Vui lòng thử lại sau 1 giờ.' },
});

/**
 * @route   POST /api/auth/register
 * @desc    Đăng ký tài khoản mới
 * @access  Public
 * @body    { username, email, password }
 */
router.post('/register', registerValidation, register);

/**
 * @route   POST /api/auth/verify-email
 * @desc    Xác minh email bằng OTP
 * @access  Public
 * @body    { email, code }
 */
router.post('/verify-email', verifyEmail);

/**
 * @route   POST /api/auth/resend-verification
 * @desc    Gửi lại mã xác minh email
 * @access  Public
 * @body    { email }
 */
router.post('/resend-verification', resendVerification);

/**
 * @route   POST /api/auth/login
 * @desc    Đăng nhập
 * @access  Public
 * @body    { email, password }
 */
router.post('/login', loginLimiter, loginValidation, login);

/**
 * @route   POST /api/auth/refresh-token
 * @desc    Làm mới access token
 * @access  Public
 * @body    { refreshToken }
 */
router.post('/refresh-token', refreshToken);

/**
 * @route   POST /api/auth/logout
 * @desc    Đăng xuất
 * @access  Public
 * @body    { refreshToken }
 */
router.post('/logout', logout);

/**
 * @route   POST /api/auth/forgot-password
 * @desc    Yêu cầu đặt lại mật khẩu
 * @access  Public
 * @body    { email }
 */
router.post('/forgot-password', forgotPasswordLimiter, forgotPassword);

/**
 * @route   POST /api/auth/reset-password
 * @desc    Đặt lại mật khẩu bằng token
 * @access  Public
 * @body    { token, password }
 */
router.post('/reset-password', resetPasswordValidation, resetPassword);

/**
 * @route   GET /api/auth/me
 * @desc    Lấy thông tin người dùng hiện tại
 * @access  Private (Bearer Token)
 */
router.get('/me', authenticate, getMe);

/**
 * @route   GET /api/auth/login-history
 * @desc    Xem lịch sử đăng nhập
 * @access  Private (Bearer Token)
 */
router.get('/login-history', authenticate, getLoginHistory);

module.exports = router;