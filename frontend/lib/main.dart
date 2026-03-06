import 'package:flutter/material.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Anki Vocab Frontend',
      home: Scaffold(
        appBar: AppBar(title: const Text('Anki Vocab Frontend')),
        body: const Center(child: Text('Placeholder Flutter frontend')),
      ),
    );
  }
}
