import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

// A simple model for a language
class Language {
  final String code;
  final String name;

  Language(this.code, this.name);
}

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Anki Vocabulary Builder',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        scaffoldBackgroundColor: const Color(0xFFE8EAF6),
      ),
      home: const VocabularyBuilderPage(),
    );
  }
}

class VocabularyBuilderPage extends StatefulWidget {
  const VocabularyBuilderPage({super.key});

  @override
  State<VocabularyBuilderPage> createState() => _VocabularyBuilderPageState();
}

class _VocabularyBuilderPageState extends State<VocabularyBuilderPage> {
  final _formKey = GlobalKey<FormState>();
  final _vocabController = TextEditingController();

  // Hardcoded language options for the dropdowns
  final List<Language> _languages = [
    Language('fr', 'French (Français)'),
    Language('en', 'English (English)'),
    Language('es', 'Spanish (Español)'),
    Language('de', 'German (Deutsch)'),
    Language('zh', 'Chinese (中文)'),
  ];

  Language? _learnLanguage;
  Language? _explainLanguage;
  String _wordCountText = '0 words';
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    // Set default languages
    _learnLanguage = _languages.firstWhere((lang) => lang.code == 'fr');
    _explainLanguage = _languages.firstWhere((lang) => lang.code == 'en');
    _vocabController.addListener(_updateWordCount);
  }

  @override
  void dispose() {
    _vocabController.removeListener(_updateWordCount);
    _vocabController.dispose();
    super.dispose();
  }

  void _updateWordCount() {
    final text = _vocabController.text.trim();
    if (text.isEmpty) {
      setState(() {
        _wordCountText = '0 words';
      });
      return;
    }
    final words = text.split('\n').where((line) => line.trim().isNotEmpty).length;
    setState(() {
      _wordCountText = '$words word${words == 1 ? '' : 's'}';
    });
  }

  Future<void> _generateCards() async {
    if (_formKey.currentState!.validate()) {
      setState(() {
        _isLoading = true;
      });

      final vocabulary = _vocabController.text.trim().split('\n').where((line) => line.trim().isNotEmpty).toList();
      
      // Replace with your actual backend URL
      // For local development, this might be http://127.0.0.1:8000
      const String apiUrl = 'http://127.0.0.1:8000/api/v1/cards/batches/';

      try {
        final response = await http.post(
          Uri.parse(apiUrl),
          headers: {
            'Content-Type': 'application/json; charset=UTF-8',
            // If you have authentication, you'll need to add an Authorization header
            // 'Authorization': 'Bearer YOUR_AUTH_TOKEN',
          },
          body: jsonEncode({
            'target_language': _learnLanguage!.code,
            'explanation_language': _explainLanguage!.code,
            'vocabulary': vocabulary,
          }),
        );

        if (response.statusCode == 201 || response.statusCode == 207) {
          // Success or partial success
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Cards generated successfully!'),
              backgroundColor: Colors.green,
            ),
          );
          _vocabController.clear();
        } else {
          // Handle error
          final errorData = jsonDecode(response.body);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Error: ${errorData['message'] ?? 'Failed to generate cards.'}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to connect to the server: $e'),
            backgroundColor: Colors.red,
          ),
        );
      } finally {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Anki Vocabulary Builder'),
        backgroundColor: const Color(0xFF3F51B5),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Language Settings Card
              Card(
                elevation: 2.0,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Language Settings', style: Theme.of(context).textTheme.titleLarge),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: _buildLanguageDropdown(
                              label: 'I want to learn *',
                              value: _learnLanguage,
                              onChanged: (newValue) {
                                setState(() {
                                  _learnLanguage = newValue;
                                });
                              },
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: _buildLanguageDropdown(
                              label: 'Explain in *',
                              value: _explainLanguage,
                              onChanged: (newValue) {
                                setState(() {
                                  _explainLanguage = newValue;
                                });
                              },
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.cyan.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.cyan.withOpacity(0.5)),
                        ),
                        child: const Row(
                          children: [
                            Icon(Icons.info_outline, color: Colors.cyan),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                'Template found: Français-(R/L) → Deck: Français::Vocabulary',
                                style: TextStyle(color: Colors.cyan),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              // Vocabulary Words Card
              Card(
                elevation: 2.0,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Vocabulary Words', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.green.shade800)),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _vocabController,
                        maxLines: 10,
                        decoration: const InputDecoration(
                          hintText: 'Enter vocabulary (one word/phrase per line) *',
                          border: OutlineInputBorder(),
                        ),
                        validator: (value) {
                          if (value == null || value.trim().isEmpty) {
                            return 'Please enter at least one word.';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Enter words in any language. Include articles/prepositions if needed (e.g., "de la pomme").\nMaximum 50 words per batch.',
                        style: TextStyle(color: Colors.grey, fontSize: 12),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(_wordCountText, style: const TextStyle(color: Colors.grey)),
                          ElevatedButton.icon(
                            onPressed: _isLoading ? null : _generateCards,
                            icon: _isLoading
                                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                                : const Icon(Icons.send),
                            label: const Text('Generate Cards'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green.shade700,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageDropdown({
    required String label,
    required Language? value,
    required ValueChanged<Language?> onChanged,
  }) {
    return DropdownButtonFormField<Language>(
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
      value: value,
      items: _languages.map((Language language) {
        return DropdownMenuItem<Language>(
          value: language,
          child: Text(language.name),
        );
      }).toList(),
      onChanged: onChanged,
      validator: (value) => value == null ? 'Please select a language.' : null,
    );
  }
}
